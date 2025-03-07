# -*- coding: utf-8 -*-
import sys
from AccessControl import getSecurityManager
from ZODB.POSException import ConflictError
from zExceptions import ExceptionFormatter, Unauthorized

from Products.CMFActivity.ActiveResult import ActiveResult
from zLOG import LOG, INFO
import six

def dumpWorkflowChain(self, ignore_default=False,
                      ignore_id_set=None, keep_order=False, batch_mode=False):
  # This method outputs the workflow chain in the format that you can
  # easily get diff like the following:
  # ---
  # Account,account_workflow
  # Account,edit_workflow
  # ...
  # ---
  # Parameters :
  # - ignore_id_set : a set with workflow ids to exclude
  # - keep_order : set to True if you would like to keep original order,
  #                default is to sort alphabetically
  # - batch_mode : used to directly return the sctructure instead of return string
  if not getSecurityManager().getUser().has_role('Manager'):
    raise Unauthorized
  if ignore_id_set is None:
    ignore_id_set = set()
  workflow_tool = self.getPortalObject().portal_workflow
  ti = workflow_tool._listTypeInfo()
  types_info = []
  for t in ti:
    id_ = t.getId()
    title = t.Title()
    if title == id_:
      title = None
    chain = None
    cbt_list = [x for x in t.getTypeWorkflowList() if not(x in ignore_id_set)]
    if not cbt_list:
      if not(ignore_default):
        chain = ['(Default)']
    elif keep_order:
      chain = cbt_list
    else:
      chain = sorted(cbt_list)
    if chain:
      types_info.append({'id': id_,
                       'title': title,
                       'chain': chain})
  types_info.sort(key=lambda x:x['id'])
  if batch_mode:
    return types_info
  output = []
  for i in types_info:
    for chain in i['chain']:
      output.append('%s,%s' % (i['id'], chain))
  return '\n'.join(output)

def checkFolderHandler(self, fixit=0, **kw):
  error_list = []
  try:
    is_btree = self.isBTree()
    is_hbtree = self.isHBTree()
  except AttributeError:
    return error_list
  message = '%s' % self.absolute_url_path()
  problem = False
  if not is_btree and not is_hbtree:
    problem = True
    message = '%s is NOT BTree NOR HBTree' % message
    if fixit:
      try:
        result = self._fixFolderHandler()
      except AttributeError:
        result = False
      if result:
        message = '%s fixed' % message
      else:
        message = '%s CANNOT FIX' % message
  if is_btree and is_hbtree:
    problem = True
    message = '%s is BTree and HBTree' % message
    if fixit:
      message = '%s CANNOT FIX' % message
  if problem:
    error_list.append(message)
    LOG('checkFolderHandler', INFO, message)
  return error_list


def MessageCatalog_getMessageDict(self):
  """
    Get Localizer's MessageCatalog instance messages.
  """
  d = {}
  for k,v in six.iteritems(self._messages):
    d[k] = v
  return d

def MessageCatalog_getNotTranslatedMessageDict(self):
  """
    Get Localizer's MessageCatalog instance messages that are NOT translated.
  """
  not_translated_message_dict = {}
  messages = MessageCatalog_getMessageDict(self)
  for k, v in six.iteritems(messages):
    if not [x for x in v.values() if x]:
      not_translated_message_dict[k] = v
  return not_translated_message_dict

def MessageCatalog_deleteNotTranslatedMessageDict(self):
  """
    Delete from  Localizer's MessageCatalog instance messages that are NOT translated.
  """
  not_translated_message_dict = MessageCatalog_getNotTranslatedMessageDict(self)
  for k,_ in not_translated_message_dict.iteritems():
    # delete message from dict
    del(self._messages[k])
  return len(not_translated_message_dict.keys())

def MessageCatalog_cleanUpMessageDict(self):
  """
    Cleans up translation dictionnaries by removing empty values
    and deleting entries without any translation from the Localizer's
    MessageCatalog instance messages.
  """
  count = 0
  for k,v in self._messages.items():
    for lang, translation in v.items():
      if len(translation) == 0 or translation == k:
        del self._messages[k][lang]
    if len(v) == 0:
      del self._messages[k]
      count += 1
  return count

def checkConversionToolAvailability(self):
  """
  Check conversion tool (oood) is available for erp5.
  This script convert an odt document into HTML and try to read
  the returned string and find out expected string
  """
  portal = self.getPortalObject()
  document_id = 'P-ERP5-TEST.Conversion.Tool.Availability-001-en.odt'
  document_path = 'portal_skins/erp5_administration/%s' % (document_id,)
  document_file = portal.restrictedTraverse(document_path)

  message = None
  severity = 0

  try:
    temp_document = self.newContent(
      portal_type='OOo Document',
      temp_object=True,
      id=document_id,
      data=document_file.data,
      source_reference=document_id)
    temp_document.convertToBaseFormat()
    _, html_result = temp_document.convert(format='html')
  except ConflictError:
    raise
  except Exception:
    #Transformation failed
    message = 'Conversion tool got unexpected error:\n%s' % ''.join(ExceptionFormatter.format_exception(*sys.exc_info()))
  else:
    #Everything goes fine, Check that expected string is present in HTML conversion
    if 'AZERTYUIOPMQ' not in html_result:
      message = 'Conversion to HTML Failed:\n%s' % (html_result,)

  active_process = self.newActiveProcess()
  result = ActiveResult()
  if message:
    severity = 1
    result.edit(detail=message)
  result.edit(severity=severity)
  active_process.postResult(result)


def filterSecurityUidDict(security_uid_dict, referenced_security_uid_set):
  """
  Removes from security_uid_dict entries whose value is not present in referenced_security_uid_set.
  Returns the list of uids dropped.
  """
  result = []
  append = result.append
  for key, value in list(security_uid_dict.items()):
    if value not in referenced_security_uid_set:
      append(value)
      del security_uid_dict[key]
  return result