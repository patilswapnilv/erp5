"""Script to execute `workflow_action`on selected documents by `uids` with optional `comment`.

This script is intended as a dialog target.

:param form_id, dialog_id: mandatory parameters of dialog form target script
:param uids: {list[int]} marks that this script takes objects from previous listbox as its input
:param workflow_action: {str} the ID of (worflow) action to execute on each object
:param comment: {str} optional comment
"""
from Products.CMFCore.WorkflowCore import WorkflowException

def stripMyYour(key):
  if key.startswith("your_") or key.startswith("my_"):
    return key.split("_", 1)[1]

MARKER = []

portal = context.getPortalObject()
request = kwargs.get("REQUEST", None) or context.REQUEST
translate = portal.Base_translateString

# Ensure the selected action is doable on received objects
document_list = [result.getObject() for result in portal.portal_catalog.searchResults(uid=uids)]
workflowable_list = []

if not workflow_action:
  return context.Base_redirect(form_id,
                               keep_items={
                                 "portal_status_message": translate("No state change possible on selected documents."),
                                 "portal_status_level": "error"})

# workflow_action_rendered is a control field to remember which workflow_action was rendered
# and we diallow submit if different action is selected and different dialog embedded
request.form['workflow_action_rendered'] = workflow_action

if kwargs.get("update_method", ""):
  return context.Base_renderForm(dialog_id,
                                 message=translate("Form updated."),
                                 level="warning",
                                 REQUEST=request)
workflow_dialog = None
if workflow_action_rendered != workflow_action:
  # if we get all fields for the workflow form - do not bother user and proceed
  try:
    workflow_dialog_id = context.Base_getFormIdForWorkflowAction(form_id, '', workflow_action, uids=uids)
    workflow_dialog = getattr(context, workflow_dialog_id)  # this can throw if form is not defined yet
    for group in workflow_dialog.get_groups():
      if group.lower() == 'hidden':
        continue
      for field in workflow_dialog.get_fields_in_group(group):
        if request.form.get("field_workflow_dialog_" + field.id, MARKER) is MARKER:
          raise AttributeError("field_workflow_dialog_" + field.id)  # direct access request.form["key"] does not throw because publisher eats the exception
  except AttributeError:
    return context.Base_renderForm(dialog_id,
                                   message=translate("Form updated."),
                                   level="warning",
                                   REQUEST=request)

for document in document_list:
  try:
    # Kato: Why does it throw an axception instead of just returning False?
    portal.portal_workflow.canDoActionFor(document, workflow_action)
  except WorkflowException as exception:
    pass
  else:
    workflowable_list.append(document)


# generate a random tag for activity grouping
tag = 'folder_workflow_action_{:d}'.format(random.randint(0, 1000))  # Kato: how come that random is accessible?
# We want change state activities to have a lower priority that erp5_deferred_style reports
# not to prevent everybody from running report while a users change state of many documents.
priority = 3
batch_size = 100

if workflow_dialog is None:
  workflow_dialog_id = context.Base_getFormIdForWorkflowAction(form_id, '', workflow_action, uids=uids)
  workflow_dialog = getattr(context, workflow_dialog_id)
workflow_action_kwargs = workflow_dialog.validate_all(request, key_prefix='field_workflow_dialog')
workflow_action_kwargs = {stripMyYour(key): value for key, value in workflow_action_kwargs.items()}
workflow_action_kwargs['workflow_action'] = workflow_action

for i in xrange(0, len(workflowable_list), batch_size):
  context.activate(activity='SQLQueue', priority=priority, tag=tag).callMethodOnObjectList(
    [doc.getRelativeUrl() for doc in workflowable_list[i:i+batch_size]],
    'Base_workflowStatusModify',
    batch_mode=True, **workflow_action_kwargs)

# activate something on the module after everything, so that user can know that
# something is happening in the background
context.activate(after_tag=tag).getTitle()

return context.Base_redirect(form_id,
  keep_items=dict(portal_status_message=translate("Workflow modification in progress.")))