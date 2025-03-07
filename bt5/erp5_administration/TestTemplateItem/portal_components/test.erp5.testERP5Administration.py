##############################################################################
#
# Copyright (c) 2004, 2005, 2006 Nexedi SARL and Contributors.
# All Rights Reserved.
#          Sebastien Robin <seb@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
##############################################################################

import unittest
import time
from Products.ERP5.tests.testInventoryAPI import InventoryAPITestCase
from DateTime import DateTime

class TestERP5Administration(InventoryAPITestCase):
  """Test for erp5_administration business template.
  """
  def getTitle(self):
    return "ERP5Administration"

  def beforeTearDown(self):
    # InventoryAPITestCase.beforeTearDown clears everything.
    # We do not want this on a ZODB test.
    pass

  def getBusinessTemplateList(self):
    """
        Same list as for Inventory API and add erp5_administration
    """
    return InventoryAPITestCase.getBusinessTemplateList(self) + ('erp5_full_text_mroonga_catalog', 'erp5_administration')

  def test_01_RunCheckStockTableAlarm(self):
    """
    Create a new alarm and check that it is able to detect any divergence
    between the predicate table and zodb objects
    """
    portal = self.getPortal()
    sql_test = portal.erp5_sql_connection.manage_test
    alarm = portal.portal_alarms.check_stock

    def checkActiveProcess(failed):
      self.tic()
      self.assertEqual(alarm.getLastActiveProcess().ActiveProcess_sense(),
                       failed)
    def checkStock(row_count):
      alarm.activeSense()
      checkActiveProcess(1)
      alarm.solve()
      checkActiveProcess(1)
      alarm.activeSense()
      checkActiveProcess(0)
      self.assertEqual(row_count, sql_test("select count(*) from stock")[0][0])

    alarm.setAlarmNotificationMode('never')
    mvt = self._makeMovement(quantity=1.23)
    self.tic()
    alarm.activeSense()
    checkActiveProcess(0)

    row_count = sql_test("select count(*) from stock")[0][0]
    sql_test("update stock set quantity=5")
    checkStock(row_count)   # alarm.solve will reindex 'mvt'
    mvt.getParentValue()._delOb(mvt.getId())
    checkStock(row_count-2) # alarm.solve will unindex 'mvt'

  def test_check_consistency_alarm(self):
    alarm = self.portal.portal_alarms.check_consistency
    inconsistent_document = self.portal.organisation_module.newContent(
        portal_type='Organisation')
    # this document will be non consistent, for PropertyTypeValidity
    inconsistent_document.title = 3
    # tic right now to make sure the person is indexed, indeed the alarm
    # could use catalog to retrieve objects to check
    self.tic()

    alarm.activeSense()
    self.tic()

    # some errors were detected
    self.assertTrue(alarm.sense())

    # this alarm has a custom report
    alarm.Alarm_viewConsistencyCheckReport()
    # which has a listbox showing all problem reported by constraints and
    # errors reported by property type validity constraint
    line_list = alarm.Alarm_viewConsistencyCheckReport.listbox.get_value(
                        'default', render_format='list')
    self.assertEqual(1, len([line for line in line_list if line.isDataLine()]))
    self.assertEqual(str(line_list[-1].getColumnProperty('getTranslatedMessage')),
      "Attribute title should be of type string but is of type " + str(int))

    # this alarm can solve, as long as the constraints can solve, this is the
    # case of PropertyTypeValidity
    alarm.solve()
    self.tic()
    self.assertEqual('3', inconsistent_document.title)

  def test_check_consistency_incremental(self):
    alarm = self.portal.portal_alarms.check_consistency.Base_createCloneDocument(
        batch_mode=True)
    alarm.edit(incremental_check=True)
    alarm.activeSense()
    self.tic()
    # create an inconsistent document
    inconsistent_document = self.portal.organisation_module.newContent(
        portal_type='Organisation')
    inconsistent_document.title = 0
    self.tic()

    # alarm report this document as not consistent
    time.sleep(2) # catalog date columns have a one second precision
    alarm.activeSense()
    self.tic()
    self.assertTrue(alarm.sense())
    result, = alarm.getLastActiveProcess().getResultList()
    constraint_message, = result.getProperty('constraint_message_list')
    self.assertEqual(inconsistent_document.getRelativeUrl(), constraint_message.object_relative_url)

    # next time the alarm run, document is not reported anymore
    alarm.activeSense()
    self.tic()
    self.assertFalse(alarm.sense())
    self.assertEqual([], alarm.getLastActiveProcess().getResultList())

    # cleanup
    self.portal.organisation_module.manage_delObjects(
        ids=[inconsistent_document.getId()])
    self.tic()

  def test_missing_category_document_constraint(self):
    person = self.portal.person_module.newContent(portal_type='Person')
    # This category does not exist
    person.setGroup('not/exist')

    # constraint reports one error
    consistency_error, = self.portal.portal_trash.newContent(
      portal_type='Missing Category Document Constraint',
      temp_object=True,
    ).checkConsistency(person)
    self.assertEqual(
      'Category group/not/exist on object %s is missing.' % person.getRelativeUrl(),
      str(consistency_error.getTranslatedMessage()))

  def test_missing_category_document_constraint_acquisition(self):
    person = self.portal.person_module.newContent(portal_type='Person')
    # This constraint is not confused by acquisition. group/level1/test_group can
    # be traversed, but category API does not use simple traversal.
    person.setCategoryList(['group/level1/test_group'])

    consistency_error, = self.portal.portal_trash.newContent(
      portal_type='Missing Category Document Constraint',
      temp_object=True,
    ).checkConsistency(person)
    self.assertEqual(
      'Category group/level1/test_group on object %s is missing.' % person.getRelativeUrl(),
      str(consistency_error.getTranslatedMessage()))

  def test_Base_viewDict(self):
    # modules and documents
    self.assertTrue(self.portal.person_module.Base_viewDict())
    self.assertTrue(self.portal.person_module.newContent().Base_viewDict())
    # base categories and categories
    base_category = self.portal.portal_categories.contentValues()[0]
    self.assertTrue(base_category.Base_viewDict())
    self.assertTrue(base_category.newContent().Base_viewDict())
    self.assertTrue(base_category.Base_viewDict()) # base category with content
    # workflows
    workflow = self.portal.portal_workflow.newContent(portal_type='Workflow')
    state = workflow.newContent(portal_type='Workflow State', title='Some State')
    self.assertTrue(state.Base_viewDict())
    transition = workflow.newContent(portal_type='Workflow Transition',
                                     title='Some Transition')
    transition.setReference('change_something')
    transition.setGuardRoleList(['Assignee', 'Assignor'])
    transition.setCategoryList('destination/' + transition.getPath())
    self.assertTrue(transition.Base_viewDict())

  def test_BusinessTemplate_getPythonSourceCodeMessageList(self):
    self.portal.portal_skins.manage_addProduct['OFS'].manage_addFolder(
      self.id())
    self.portal.portal_skins[
      self.id()].manage_addProduct['PythonScripts'].manage_addPythonScript(
        'Base_testSourceCode')
    self.portal.portal_skins[self.id()]['Base_testSourceCode'].write(
      '''# empty line
script_error()
''')
    self.portal.portal_components.newContent(
      portal_type='Extension Component',
      id='extension.erp5.DummyComponentForSourceCodeTest',
      reference='DummyComponentForSourceCodeTest',
      version='erp5',
      text_content='''# empty line
component_error()
''')
    bt = self.portal.portal_templates.newContent(
      portal_type='Business Template', )
    bt.setTemplateSkinIdList([self.id()])
    bt.setTemplateExtensionIdList(
      ['extension.erp5.DummyComponentForSourceCodeTest'])
    message_list = bt.BusinessTemplate_getPythonSourceCodeMessageList()
    location_and_message_list = [(m.location, m.message) for m in message_list]
    self.assertIn(
      (
        'portal_skins/%s/Base_testSourceCode:2:0' % self.id(),
        "Undefined variable 'script_error' (undefined-variable)"),
      location_and_message_list)
    self.assertIn(
      (
        'portal_components/extension.erp5.DummyComponentForSourceCodeTest:2:0',
        "Undefined variable 'component_error' (undefined-variable)"),
      location_and_message_list)


  def test_check_site_modification(self):
    # remove second, obj's modification in erp5 don't have seconds
    check_date = DateTime(DateTime().strftime('%Y-%m-%d %H:%M'))
    active_process = self.portal.portal_activities.newActiveProcess()
    self.portal.Base_checkSiteDailyModification(
      active_process=active_process.getRelativeUrl(),
      check_date = check_date
    )
    result_list  = [x.detail for x in active_process.getResultList()]
    message_list = [
      'erp5_administration/Base_checkSiteDailyModification is modified',
      'erp5_administration/BusinessTemplate_viewCheckPythonCodeDialog is modified',
      'portal_workflow/edit_workflow is modified',
      'portal_workflow/edit_workflow/state_current is modified',
      'portal_workflow/preference_interaction_workflow is modified'
    ]
    for message in message_list:
      self.assertNotIn(message, result_list)

    self.portal.portal_skins.erp5_administration.Base_checkSiteDailyModification.ZPythonScript_setTitle('%s' % check_date)
    self.portal.portal_skins.erp5_administration.Base_checkSiteDailyModification.ZPythonScript_setTitle('')
    self.portal.portal_skins.erp5_administration.BusinessTemplate_viewCheckPythonCodeDialog.manage_addProduct['Formulator'].manage_addField('my_title', 'Title', 'StringField')
    self.portal.portal_skins.erp5_administration.BusinessTemplate_viewCheckPythonCodeDialog.manage_delObjects('my_title')
    new_comment = 'Test %s' % check_date
    self.portal.portal_workflow.preference_interaction_workflow.edit(
      comment = new_comment
    )
    self.portal.portal_workflow.edit_workflow.edit(
      comment = new_comment
    )
    self.portal.portal_workflow.edit_workflow.state_current.edit(
      comment = new_comment
    )

    self.tic()
    self.portal.Base_checkSiteDailyModification(
      active_process=active_process.getRelativeUrl(),
      check_date = check_date
    )
    result_list = [x.detail for x in active_process.getResultList()]
    for message in message_list:
      self.assertIn(message, result_list)



def test_suite():
  suite = unittest.TestSuite()
  suite.addTest(unittest.makeSuite(TestERP5Administration))
  return suite
