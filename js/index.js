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
  const appId = 107712229
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

  const comp = new algosdk.AtomicTransactionComposer();

  comp.addMethodCall({
    method: contract.getMethodByName("deposit"),
    methodArgs: [
      {
        txn: new Transaction({
          from: acct.addr,
          to: appAddress,
          amount: 200000,
          ...suggestedParams,
        }),
        signer: algosdk.makeBasicAccountTransactionSigner(acct),
      },
    ],
    ...commonParams,
  });
  const results = await comp.execute(client, 2);
  for (const result of results.methodResults) {
    console.log(`${result.method.name} => ${result.returnValue}`);
  }

})();
