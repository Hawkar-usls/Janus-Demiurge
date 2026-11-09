#!/usr/bin/env node
/** OPEN-FUTURE-009B: BLS-verified 128 distinct Quicknet rounds. No selection. */
import fs from "node:fs";
import {createHash} from "node:crypto";
import {quicknetClient,fetchBeacon} from "drand-client";

const HASH="52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971";
const PUB="83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a";
const GENESIS=1692803367;
const PERIOD=3;

async function main(){
  const [precommitPath, outputPath]=process.argv.slice(2);
  if(!precommitPath||!outputPath||fs.existsSync(outputPath))throw Error("BAD_ARGS_OR_REFUSE_OVERWRITE");
  const obj=JSON.parse(fs.readFileSync(precommitPath,"utf8"));
  const p=obj.payload;
  if(p?.lane!=="OPEN-FUTURE-009B"||p.phase!=="EARLY_PRECOMMIT"||
     p.quicknet_hash!==HASH||p.quicknet_genesis_unix!==GENESIS||
     p.quicknet_period_seconds!==PERIOD||p.n_distinct_rounds!==128||
     !Array.isArray(p.target_rounds)||p.target_rounds.length!==128 ||
     p.target_rounds.some((x,i)=>!Number.isSafeInteger(x)||x<1||
             (i>0&&x-p.target_rounds[i-1]!==20)))throw Error("UNTRUSTED_PRECOMMIT");
  if(Date.now()< (p.last_release_unix+15)*1000)throw Error("TARGET_ROUNDS_STILL_IN_FUTURE");
  const client=quicknetClient(); // official drand-client@1.4.2; BLS verification enabled
  const info=await client.chain().info();
  if(info.hash!==HASH||info.public_key!==PUB||info.genesis_time!==GENESIS||
     info.period!==PERIOD||info.metadata?.beaconID!=="quicknet")
     throw Error("PINNED_DRAND_CHAIN_INFO_CHANGED");
  const beacons=[];
  // Bounded 128 requests, sequential and no retries/round substitution.
  for(const round of p.target_rounds){
    const b=await fetchBeacon(client,round); // mandatory built-in BLS verification
    if(b.round!==round||!/^[0-9a-f]+$/.test(b.signature))throw Error("UNEXPECTED_BEACON_ROUND_OR_SIGNATURE");
    const recovered=createHash("sha256").update(Buffer.from(b.signature,"hex")).digest("hex");
    if(recovered!==b.randomness)throw Error("INVALID_BEACON_SIGNATURE_HASH");
    beacons.push({round:b.round,randomness:b.randomness,
                  signature:b.signature,signature_verified_by_pinned_client:true});
  }
  const receipt={schema:"janus.ocean.open_future_signed_beacons_009b.v1",
                 chain_hash:HASH,signature_verification:"DRAND_CLIENT_BLS_PINNED",
                 verifier_package:"drand-client@1.4.2",
                 target_rounds:p.target_rounds,beacons,
                 created_at_self_reported:new Date().toISOString(),
                 omitted_rounds:0,retrocausality_proven:false};
  fs.mkdirSync(outputPath.split("/").slice(0,-1).join("/")||".",{recursive:true});
  fs.writeFileSync(outputPath,JSON.stringify(receipt,null,2)+"\n",{flag:"wx"});
  console.log(JSON.stringify({status:"ALL_128_DRAND_BLS_VERIFIED",count:beacons.length}));
}
main().catch(e=>{console.error("DRAND_009B_FAIL_CLOSED",e.message);process.exitCode=1});
