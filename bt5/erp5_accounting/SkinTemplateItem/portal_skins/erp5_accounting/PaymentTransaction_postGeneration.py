from Products.ERP5Type.Message import translateString

payment_transaction = context
payment_transaction.AccountingTransaction_roundDebitCredit()

# initialize accounting_workflow to planned state
if payment_transaction.getSimulationState() == "draft":
  payment_transaction.plan(comment=translateString("Initialised by Delivery Builder."))
