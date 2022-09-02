from pyteal import *

is_creator = Txn.sender() == Global.creator_address()

transfer_balance_to_lost = App.globalPut(
    Bytes("lost"),
    App.globalGet(Bytes("lost")) + App.localGet(Txn.sender(), Bytes("balance"))
)

router = Router(
    "algo-lock",
    BareCallActions(
        no_op=OnCompleteAction.create_only(Approve()),
        opt_in=OnCompleteAction.always(Approve()),
        close_out=OnCompleteAction.call_only(transfer_balance_to_lost),
        update_application=OnCompleteAction.always(Assert(is_creator)),
        delete_application=OnCompleteAction.always(Assert(is_creator)),
        clear_state=OnCompleteAction.call_only(transfer_balance_to_lost),
    )
)

@router.method
def deposit(ptxn: abi.PaymentTransaction, *, output: abi.Uint64) -> Expr:
    return Seq(
        Assert(ptxn.get().type_enum == TxnType.Payment),
        Assert(ptxn.get().sender() == Txn.sender()),
        Assert(ptxn.get().receiver() == Global.current_application_address()),
        Assert(ptxn.get().amount() > Int(0)),
        App.localPut(
            Txn.sender(),
            Bytes("balance"),
            App.localGet(Txn.sender(), Bytes("balance")) + ptxn.get().amount(),
        ),
        output.set(ptxn.get().amount()),
    )

@router.method
def getBalance(user: abi.Account, *, output: abi.Uint64) -> Expr:
    return output.set(
        App.localGet(user.address(), Bytes("balance"))
    )

@router.method
def withdraw(recipient: abi.Account, *, output: abi.Uint64) -> Expr:
    return Seq(
        output.set(
            App.localGet(Txn.sender(), Bytes("balance"))
        ),
        Assert(output.get() > Int(0)),
        App.localPut(
            Txn.sender(),
            Bytes("balance"),
            Int(0)
        ),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: recipient.address(),
                TxnField.amount: output.get(),
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),
    )


if __name__ == "__main__":
    import os
    import json

    path = os.path.dirname(os.path.abspath(__file__))

    # we use compile program here to get the resulting teal code and Contract definition
    # similarly we could use build_program to return the AST for approval/clear and compile it
    # ourselves, but why?
    approval, clear, contract = router.compile_program(
        version=6, optimize=OptimizeOptions(scratch_slots=True)
    )

    # Dump out the contract as json that can be read in by any of the SDKs
    with open(os.path.join(path, "algo-lock.json"), "w") as f:
        f.write(json.dumps(contract.dictify(), indent=2))

    # Write out the approval and clear programs
    with open(os.path.join(path, "approval.teal"), "w") as f:
        f.write(approval)

    with open(os.path.join(path, "clear.teal"), "w") as f:
        f.write(clear)
