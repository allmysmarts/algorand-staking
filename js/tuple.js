import dotenv from 'dotenv';
dotenv.config()

import algosdk, { decodeAddress, Transaction } from "algosdk";
import * as fs from "fs";
import utils from './utils.js'

const algod_token =
  "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const algod_host = "https://testnet-api.algonode.cloud";

/**
 * Wait for confirmation — timeout after 2 rounds
 */
 async function verboseWaitForConfirmation(client, txnId) {
  console.log('Awaiting confirmation (this will take several seconds)...');
  const roundTimeout = 2;
  const completedTx = await utils.waitForConfirmation(
    client,
    txnId,
    roundTimeout
  );
  console.log('Transaction successful.');
  return completedTx;
}

(async function() {
  const client = new algosdk.Algodv2(algod_token, algod_host, '');
  const acct = algosdk.mnemonicToSecretKey(process.env['MNEMONIC'] || '');
  const buff = fs.readFileSync("../algo-lock.json");
  const contract = new algosdk.ABIContract(JSON.parse(buff.toString()));
  const appId = 108204869
  const appAddress = algosdk.getApplicationAddress(appId)
  console.log('application address: ', appAddress)

  // get suggested params
  const suggestedParams = await client.getTransactionParams().do();

  // account info
  const accountInfo = await client.accountInformation(acct.addr, appId).do()
  if (
    accountInfo['apps-local-state'].length >0 &&
    (accountInfo['apps-local-state'].find(app => app.id == appId))
  ) {
    console.log('Already opted in.')
    console.log('account info: ', JSON.stringify(accountInfo['apps-local-state'], null, 4))
  } else {
    // opt-in application
    const optInTxn = algosdk.makeApplicationOptInTxn(
      acct.addr,
      suggestedParams,
      appId
    )
    const signedOptInTxn = optInTxn.signTxn(acct.sk);
    const { txId: optInTxId } = await client
      .sendRawTransaction(signedOptInTxn)
      .do();
    await verboseWaitForConfirmation(client, optInTxId)
  }

  // abi call
  const commonParams = {
    appID: appId,
    sender: acct.addr,
    suggestedParams,
    signer: algosdk.makeBasicAccountTransactionSigner(acct),
  };
/*
  const comp = new algosdk.AtomicTransactionComposer();

  comp.addMethodCall({
    method: contract.getMethodByName("storeTuple"),
    methodArgs: [
      253,
    ],
    ...commonParams,
  });
  const results = await comp.execute(client, 2);
  for (const result of results.methodResults) {
    console.log(`${result.method.name} => ${result.returnValue}`);
  }

  const comp2 = new algosdk.AtomicTransactionComposer();
  comp2.addMethodCall({
    method: contract.getMethodByName("loadTuple"),
    ...commonParams,
  });
  const results2 = await comp2.execute(client, 2);
  for (const result of results2.methodResults) {
    console.log(`${result.method.name} => ${result.returnValue}`);
  }

  const comp = new algosdk.AtomicTransactionComposer(); 
  comp.addMethodCall({
    method: contract.getMethodByName("storeNumbers"),
    methodArgs: [
      [8657302, 34, 255],
    ],
    ...commonParams,
  });

  comp.addMethodCall({
    method: contract.getMethodByName("loadNumbers"),
    ...commonParams,
  });
  const results = await comp.execute(client, 2);
  for (const result of results.methodResults) {
    console.log(`${result.method.name} => ${result.returnValue}`);
  }
*/
  const comp = new algosdk.AtomicTransactionComposer();

  comp.addMethodCall({
    method: contract.getMethodByName("pushNumbers"),
    methodArgs: [
      138,
    ],
    ...commonParams,
  });
  
  comp.addMethodCall({
    method: contract.getMethodByName("readNumbers"),
    ...commonParams,
  });
  const results = await comp.execute(client, 2);
  
  for (const result of results.methodResults) {
    console.log(`${result.method.name} => ${result.returnValue}`);
  }
})();
