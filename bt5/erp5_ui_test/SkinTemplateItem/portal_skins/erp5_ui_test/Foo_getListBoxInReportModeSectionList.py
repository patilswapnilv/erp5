"""Return a list of Report Section"""
from Products.ERP5Form.Report import ReportSection
from six.moves import range
kw = {
  'path': context.getPhysicalPath(),
  'form_id': 'Foo_viewDummyListBox',
  'level': 1,
#  'listbox_display_mode': 'FlatListMode',
#  'selection_params': {},
  'temporary_selection': False,
}
return [ReportSection(**kw) for _ in range(3)]
