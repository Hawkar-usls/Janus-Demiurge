#!/usr/bin/env node
/**
 * JANUS R4 future externally signed drand Quicknet challenge.
 * The verified drand-client@1.4.2 checks the exact PRECOMMITTED future round.
 * No quantum hardware, no physically past-directed message.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {setTimeout as sleep} from 'node:timers/promises';
import {HttpCachingChain,HttpChainClient,fetchBeacon} from 'drand-client';

const CHAIN_HASH='52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971';
const PUBLIC_KEY='83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a';
const GENESIS=1692803367;
const PERIOD=3;

function check(condition,message){if(!condition)throw Error(message);}
async function readJson(filename){return JSON.parse(await fs.readFile(filename,'utf8'));}
function verifyPlan(plan){
  check(plan && plan.schema==='janus.external_beacon.plan.r4','INVALID_PLAN');
  check(plan.beacon_chain_id==='quicknet' &&
        plan.beacon_chain_hash===CHAIN_HASH,'CHAIN_HASH_MISMATCH');
  check(Number.isInteger(plan.target_round) && plan.target_round>0,'INVALID_ROUND');
  check(Number.isFinite(plan.early_created_epoch) &&
        Number.isFinite(plan.target_release_epoch) &&
        plan.target_release_epoch===GENESIS+(plan.target_round-1)*PERIOD,
        'UNEXPECTED_RELEASE_EPOCH');
  check(plan.target_release_epoch-plan.early_created_epoch>=180,
        'FUTURE_ROUND_NOT_PRECOMMITTED_180_SEC_AHEAD');
  check(typeof plan.trial_id==='string' &&
        /^[0-9]{1,29}$/.test(plan.trial_id),'INVALID_ID');
  check(plan.forecast_string_not_in_plan===true &&
        !Object.prototype.hasOwnProperty.call(plan,'forecast_bits'),
        'LATE_GENERATOR_MUST_NOT_READ_EARLY_FORECAST');
  check(typeof plan.forecast_sha256==='string' &&
        /^[0-9a-f]{64}$/.test(plan.forecast_sha256),'INVALID_FORECAST_DIGEST');
}

async function verifiedBeacon(round){
  const options={
    disableBeaconVerification:false,
    noCache:true,
    apiVersion:'v1',
    chainVerificationParams:{chainHash:CHAIN_HASH,publicKey:PUBLIC_KEY}
  };
  const chain=new HttpCachingChain(
    'https://api.drand.sh/'+CHAIN_HASH,options
  );
  const info=await chain.info();
  check(info.hash===CHAIN_HASH && info.public_key===PUBLIC_KEY &&
        info.genesis_time===GENESIS && info.period===PERIOD &&
        info.schemeID==='bls-unchained-g1-rfc9380',
        'PINNED_BEACON_CHAIN_METADATA_MISMATCH');
  const client=new HttpChainClient(chain,options);
  let last;
  for(let i=0;i<8;i++){
    try{
      const b=await fetchBeacon(client,round);
      check(b.round===round,'WRONG_BEACON_ROUND');
      check(typeof b.randomness==='string' && /^[0-9a-f]{64}$/.test(b.randomness),
            'INVALID_RANDOMNESS_HEX');
      check(typeof b.signature==='string' && /^[0-9a-f]{96}$/.test(b.signature),
            'INVALID_QUICKNET_G1_SIGNATURE');
      check(createHash('sha256').update(Buffer.from(b.signature,'hex'))
             .digest('hex')===b.randomness,'SHA_SIGNATURE_MISMATCH');
      return b; // fetchBeacon internally checks the pinned BLS signature.
    }catch(e){
      last=e;
      if(i===7)break;
      await sleep(3500);
    }
  }
  throw last;
}

async function main(){
  const [mode, planPath, futureOrReport, optionalOutput] = process.argv.slice(2);
  check(mode==='future'||mode==='verify-existing','UNKNOWN_MODE');
  const plan=await readJson(planPath);
  verifyPlan(plan);
  const waitMs=Math.ceil(plan.target_release_epoch*1000-Date.now());
  check(waitMs<5*60*1000,'ROUND_TOO_FAR_IN_FUTURE');
  if(waitMs>0)await sleep(waitMs+2500);
  const beacon=await verifiedBeacon(plan.target_round);
  const retrieved=Date.now()/1000;
  check(retrieved>=plan.target_release_epoch,'BEACON_BEFORE_RELEASE');
  if(mode==='future'){
    const result={
      schema:'janus.external_beacon.future.r4',
      trial_id:plan.trial_id,
      beacon_chain_id:'quicknet',
      beacon_chain_hash:CHAIN_HASH,
      target_round:plan.target_round,
      signature:beacon.signature,
      randomness:beacon.randomness,
      cryptographic_bls_verification:true,
      verified_by:'drand-client@1.4.2',
      retrieved_epoch:retrieved,
      read_early_forecast_bits:false,
      physical_retrocausality_proven:false
    };
    await fs.mkdir(path.dirname(futureOrReport),{recursive:true});
    await fs.writeFile(futureOrReport,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
    console.log(JSON.stringify({stage:'externally_signed_future',round:beacon.round,
       randomness:beacon.randomness,bls_verified:true,physical_retrocausality:false}));
  }else{
    check(typeof optionalOutput==='string' && optionalOutput.length>0,
          'REQUIRE_OUTPUT_PATH');
    const previous=await readJson(futureOrReport);
    check(previous.target_round===beacon.round &&
          previous.signature===beacon.signature &&
          previous.randomness===beacon.randomness &&
          previous.cryptographic_bls_verification===true,
          'INDEPENDENT_BLS_RECHECK_MISMATCH');
    const result={
      schema:'janus.external_beacon.independent_reverify.r4',
      trial_id:plan.trial_id,
      exact_round:beacon.round,
      independent_second_fetch_and_BLS_verification_pass:true,
      chain_hash_pinned:CHAIN_HASH,
      physical_backward_signal:false
    };
    await fs.mkdir(path.dirname(optionalOutput),{recursive:true});
    await fs.writeFile(optionalOutput,JSON.stringify(result,null,2)+'\n',
                       {flag:'wx'});
    console.log(JSON.stringify({stage:'reverified',round:beacon.round,
       bls_verified:true,physical_retrocausality:false}));
  }
}
main().catch(e=>{console.error('JANUS R4 FAIL CLOSED:',e);process.exitCode=1;});
