"""Return python source code in business template
"""
import json
import six

class Message:
  """A python code linter message, with a link to edit the source code.

  Supports both being displayed in a listbox and being printed.
  """
  def __init__(self, location, message, edit_url, jio_key=None):
    self.location = location
    self.message = message
    self.edit_url = edit_url
    self.jio_key = jio_key

  def getListItemUrl(self, *args, **kw):
    return self.edit_url

  def getListItemUrlDict(self, *args, **kw):
    if self.jio_key is None:
      # Use raw portal skins edition
      return {
        'command': 'raw',
        'options': {
          'url': self.edit_url
        }
      }
    else:
      # Stay in ERP5JS
      # XXX How to focus on the line to change directly?
      return {
        'command': 'push_history',
        'options': {
          'jio_key': self.jio_key,
          'editable': True,
        }
      }

  def __repr__(self):
    return "{}:{}".format(self.location, self.message)


portal = context.getPortalObject()
line_list = []

def checkPythonScript(script_instance, script_path):
  """Check a python script, adding messages to global `line_list`
  """
  # printed is from  RestrictedPython.RestrictionMutator the rest comes from
  # RestrictedPython.Utilities.utility_builtins
  extra_builtins = ['printed', 'same_type', 'string', 'sequence', 'random',
    'DateTime', 'whrandom', 'reorder', 'sets', 'test', 'math']
  code = script_instance.body()
  if six.PY2:
    code = six.text_type(code, 'utf8')
  for annotation in json.loads(portal.ERP5Site_checkPythonSourceCodeAsJSON(
      {'bound_names': extra_builtins +
         script_instance.getBindingAssignments().getAssignedNamesInOrder(),
       'params': script_instance.params(),
       'code': code
      }))['annotations']:
    annotation["script_path"] = script_path
    line_list.append(
      Message(
        location="{script_path}:{row}:{column}".format(**annotation),
        message=annotation['text'],
        edit_url="{script_path}/manage_workspace?line={row}".format(**annotation),))

def checkComponent(component_instance):
  """Check a component, adding messages to global `line_list`
  """
  component_relative_url = component_instance.getRelativeUrl()
  for consistency_message in component_instance.checkConsistency():
    line_list.append(
      Message(
        location=component_relative_url,
        message=consistency_message.getMessage().translate(),
        edit_url=component_relative_url,
        jio_key=component_relative_url,),)
  code = component_instance.getTextContent()
  if six.PY2:
    code = six.text_type(code, 'utf8')
  for annotation in json.loads(portal.ERP5Site_checkPythonSourceCodeAsJSON(
        {'code': code}))['annotations']:
    annotation['component_path'] = component_relative_url
    line_list.append(
      Message(
        location="{component_path}:{row}:{column}".format(**annotation),
        message=annotation["text"],
        edit_url="{component_path}?line={row}".format(**annotation),
        jio_key=annotation['component_path'],),)

# Check scripts
script_container_list = []
for skin_id in context.getTemplateSkinIdList():
  script_container_list.append(portal.portal_skins[skin_id])
for workflow_id in context.getTemplateWorkflowIdList():
  script_container_list.append(portal.portal_workflow[workflow_id])

for script_container in script_container_list:
  for script_path, script_instance in portal.ZopeFind(
      script_container, obj_metatypes=[
          'Script (Python)',
          'ERP5 Python Script',
          'ERP5 Workflow Script',
      ], search_sub=1):
    checkPythonScript(script_instance, "%s/%s" % (
      portal.portal_url.getRelativeUrl(script_container), script_path))

# Check components
for component_id in (
    context.getTemplateExtensionIdList()
    + context.getTemplateDocumentIdList()
    + context.getTemplateMixinIdList()
    + context.getTemplateTestIdList()
    + context.getTemplateModuleComponentIdList()
    + context.getTemplateToolComponentIdList()
  ):
  checkComponent(portal.portal_components[component_id])

return line_list
