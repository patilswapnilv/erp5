from Products.ERP5Type.Utils import ensure_list
editable_property_list = ensure_list(zip(*context.BudgetLine_getEditablePropertyList()))[0]

if 'destination_credit' in editable_property_list:
  return -1
if 'destination_asset_credit' in editable_property_list:
  return -1
return 1
