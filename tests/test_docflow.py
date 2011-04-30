# -*- coding: utf-8 -*-

import unittest
from docflow import (DocumentWorkflow, WorkflowState, WorkflowStateGroup,
    WorkflowStateException, WorkflowTransitionException, WorkflowPermissionException)

class MyDocument(object):
    def __init__(self):
        self.status = None
        self.email = ''
        self.email_verified = False

class MyDocumentWorkflow(DocumentWorkflow):
    """
    Workflow for MyDocument
    """

    # Attribute in MyDocument to store status in.
    # Use ``state_key`` if MyDocument is a dictionary,
    # as is typical with NoSQL JSON-based databases.
    state_attr = 'status'

    # Define a state. First parameter is the state tracking value,
    # stored in state_attr
    draft     = WorkflowState(0, title="Draft",     description="Only owner can see it")
    pending   = WorkflowState(1, title="Pending",   description="Pending review")
    published = WorkflowState(2, title="Published", description="Published")
    withdrawn = WorkflowState(3, title="Withdrawn", description="Withdrawn by owner")
    rejected  = WorkflowState(4, title="Rejected",  description="Rejected by reviewer")

    # Define a state group
    not_published = WorkflowStateGroup([0, 1], title="Not Published")

    def permissions(self, context=None):
        """
        Return permissions available to current user. A permission can be any hashable token.
        """
        if context and context['is_admin']:
            return ['can_publish']
        else:
            return []

    # Define a transition. There can be multiple transitions connecting any two states.
    # Parameters: newstate, permission, title, description
    @draft.transition(pending, None, title='Submit')
    def submit(self, context=None):
        """
        Change workflow state from draft to pending.
        """
        # Do something here
        # ...
        pass # State will be changed automatically if we don't raise an exception

    @pending.transition(published, 'can_publish', title="Publish")
    def publish(self, context=None):
        """
        Publish the document.
        """
        # Also do something here
        # ...
        if not self._document.email_verified:
            raise WorkflowTransitionException("Email address is not verified.")


class MyDocumentWorkflowExtraState(MyDocumentWorkflow):
    expired = WorkflowState(5, title="Expired")


class TestWorkflow(unittest.TestCase):
    def test_no_default_state(self):
        doc = MyDocument()
        self.assertRaises(WorkflowStateException, MyDocumentWorkflow, doc)

    def test_states(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        self.assertEqual(wf.state, wf.draft)

    def test_transition(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        wf.submit()
        self.assertEqual(wf.state, wf.pending)

    def test_invalid_transitions(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        self.assertRaises(WorkflowTransitionException, wf.publish)
        wf.submit()
        self.assertEqual(wf.state, wf.pending)
        self.assertRaises(WorkflowPermissionException, wf.publish)
        self.assertRaises(WorkflowTransitionException, wf.publish, context={'is_admin': True})

    def test_transition_sequence(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        wf.submit()
        doc.email_verified = True
        wf.publish(context={'is_admin': True})
        self.assertEqual(wf.state, wf.published)

    def test_inherited_workflow(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflowExtraState(doc)
        self.assertEqual(len(wf.all_states()), 6)

    def test_state_boolean(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        self.assertEqual(wf.draft(), True)

    def test_state_group(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        self.assertEqual(wf.not_published(), True)

if __name__=='__main__':
    unittest.main()
