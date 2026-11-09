#!/usr/bin/env node
/** JANUS blind drand pilot: only official signed Quicknet public randomness.
 * Uses pinned drand-client@1.4.2 v1 HTTP endpoint and verifies every beacon
 * against the pinned Quicknet public key and chain hash.
 * No secrets, no dynamic endpoints, no signature-verification bypasses.
 */
import fs from "node:fs";
import {createHash} from "node:crypto";
import {quicknetClient,fetchBeacon} from "drand-client";

const HASH="52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971";
const PUBLIC_KEY="83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a";
const GENESIS=1692803367;
const PERIOD=3;

function writeOnce(path,obj) {
  if (fs.existsSync(path)) throw Error("REFUSE_OVERWRITE_BEACON_RECEIPT");
  fs.mkdirSync(path.split("/").slice(0,-1).join("/")||".",{recursive:true});
  fs.writeFileSync(path,JSON.stringify(obj,null,2)+"\n",{flag:"wx"});
}

async function main() {
  const [mode,arg,path]=process.argv.slice(2);
  if (!["latest","target"].includes(mode)||!path) throw Error("INVALID_MODE");
  const client=quicknetClient(); // built-in pinned public key; verification ON
  const info=await client.chain().info();
  if(info.hash!==HASH||info.public_key!==PUBLIC_KEY
      ||info.genesis_time!==GENESIS||info.period!==PERIOD
      ||info.metadata?.beaconID!=="quicknet"){
    throw Error("QUICKNET_CHAIN_METADATA_MISMATCH");
  }
  let target;
  if(mode==="target"){
    if(!arg) throw Error("MISSING_EARLY_COMMITMENT");
    const early=JSON.parse(fs.readFileSync(arg,"utf-8"));
    if(early.beacon_chain_hash!==HASH||early.phase!=="EARLY_PRECOMMIT")throw Error("INVALID_EARLY_COMMITMENT");
    target=early.predeclared_future_round;
    if(!Number.isSafeInteger(target)||target<1) throw Error("INVALID_LOCKED_FUTURE_ROUND");
  } else if(mode==="latest" && arg!=="-") {
    throw Error("LATEST_ONLY_DASH_MARKER_ACCEPTED");
  }
  // fetchBeacon performs BLS signature verification, including expected round.
  // If HTTP source is wrong, its public key drifts, or signature is invalid,
  // the official library fails and no beacon output is written.
  const beacon=await fetchBeacon(client,target);
  if(target!==undefined&&beacon.round!==target)throw Error("WRONG_FUTURE_ROUND");
  if(!/^[0-9a-f]+$/.test(beacon.signature))throw Error("MALFORMED_SIGNATURE");
  const derived=createHash("sha256").update(Buffer.from(beacon.signature,"hex")).digest("hex");
  if(derived!==beacon.randomness)throw Error("RANDOMNESS_SIGNATURE_SHA_MISMATCH");
  const result={
    schema:"janus.ocean.drand_quicknet_signed_beacon.v1",
    chain_hash:HASH,
    genesis_time:GENESIS,
    period:PERIOD,
    round:beacon.round,
    randomness:beacon.randomness,
    signature:beacon.signature,
    signature_verified_by_pinned_client:true,
    drand_client_version:"1.4.2",
    direct_beacon_http_source:"https://api.drand.sh/"+HASH,
    recorded_at_unix_ms:Date.now(),
  };
  writeOnce(path,result);
  console.log(JSON.stringify({status:"SIGNED_QUICKNET_BEACON_OK",
       chain_hash:HASH,round:beacon.round,
       signature_verified_by_pinned_client:true,
       provider_response_not_used_for_retrocausal_claim:true}));
}
main().catch(e=>{
  console.error("DRAND_SIGNATURE_OR_CONNECTION_VALIDATION_FAILED");
  process.exitCode=1;
});
