import sys
from dotenv import dotenv_values
from typing import Dict, Union, List, Any, Optional
from algosdk import account, encoding, mnemonic
from algosdk.future import transaction
from algosdk.logic import get_application_address
from algosdk.v2client.algod import AlgodClient
from base64 import b64decode

CONFIG = dotenv_values(".env")

class Account:
    def __init__(self, privateKey: str) -> None:
        self.sk = privateKey
        self.addr = account.address_from_private_key(privateKey)
    
    def getAddress(self) -> str:
        return self.addr
    
    def getPrivateKey(self) -> str:
        return self.sk
    
    def getMnemonic(self) -> str:
        return mnemonic.from_private_key(self.sk)
    
    @classmethod
    def DefaultAccount(cls) -> "Account":
        return cls(CONFIG["PRIVATE_KEY"])

    @classmethod
    def FromMnemonic(cls, m: str) -> "Account":
        return cls(mnemonic.to_private_key(m))

class PendingTxnResponse:
    def __init__(self, response: Dict[str, Any]) -> None:
        self.poolError: str = response["pool-error"]
        self.txn: Dict[str, Any] = response["txn"]

        self.applicationIndex: Optional[int] = response.get("application-index")
        self.assetIndex: Optional[int] = response.get("asset-index")
        self.closeRewards: Optional[int] = response.get("close-rewards")
        self.closingAmount: Optional[int] = response.get("closing-amount")
        self.confirmedRound: Optional[int] = response.get("confirmed-round")
        self.globalStateDelta: Optional[Any] = response.get("global-state-delta")
        self.localStateDelta: Optional[Any] = response.get("local-state-delta")
        self.receiverRewards: Optional[int] = response.get("receiver-rewards")
        self.senderRewards: Optional[int] = response.get("sender-rewards")

        self.innerTxns: List[Any] = response.get("inner-txns", [])
        self.logs: List[bytes] = [b64decode(l) for l in response.get("logs", [])]

CLIENT = AlgodClient(CONFIG["ALGOD_API_TOKEN"], CONFIG["ALGOD_SERVER_ADDRESS"])
ACCOUNT = Account.FromMnemonic(CONFIG["MNEMONIC"])

def fullyCompileContract(client: AlgodClient, teal: str) -> bytes:
    response = client.compile(teal)
    return b64decode(response["result"])

def waitForTransaction(
    client: AlgodClient, txID: str, timeout: int = 10
) -> PendingTxnResponse:
    lastStatus = client.status()
    lastRound = lastStatus["last-round"]
    startRound = lastRound

    while lastRound < startRound + timeout:
        pending_txn = client.pending_transaction_info(txID)

        if pending_txn.get("confirmed-round", 0) > 0:
            return PendingTxnResponse(pending_txn)

        if pending_txn["pool-error"]:
            raise Exception("Pool error: {}".format(pending_txn["pool-error"]))

        lastStatus = client.status_after_block(lastRound + 1)

        lastRound += 1

    raise Exception(
        "Transaction {} not confirmed after {} rounds".format(txID, timeout)
    )

if __name__ == "__main__":
    f = open("approval.teal", "r")
    approval_program = f.read()
    f = open("clear.teal", "r")
    clear_program = f.read()

    print("Compiling contract ...")
    approval = fullyCompileContract(CLIENT, approval_program)
    clear = fullyCompileContract(CLIENT, clear_program)

    # Deploy contract
    suggested_params = CLIENT.suggested_params()
    global_schema = transaction.StateSchema(num_uints=1, num_byte_slices=0)
    local_schema = transaction.StateSchema(num_uints=2, num_byte_slices=4)
    signed_txn = transaction.ApplicationCreateTxn(
        sender=ACCOUNT.getAddress(),
        sp=suggested_params,
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        global_schema=global_schema,
        local_schema=local_schema,
    ).sign(ACCOUNT.getPrivateKey())

    print("Sending transaction to create contract ...")
    CLIENT.send_transaction(signed_txn)

    response = waitForTransaction(CLIENT, signed_txn.get_txid())
    assert response.applicationIndex is not None and response.applicationIndex > 0

    print("Created application ID: {}".format(response.applicationIndex))
    