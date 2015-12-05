# -*- coding: utf-8 -*-

import six
import unittest
from docflow import (DocumentWorkflow, WorkflowState, WorkflowStateGroup, WorkflowException,
                     WorkflowStateException, WorkflowTransitionException, WorkflowPermissionException,
                     WorkflowTransition, InteractiveTransition)


# --- Test document -----------------------------------------------------------

class MyDocument(object):
    def __init__(self):
        self.status = None
        self.email = ''
        self.email_verified = False
        self.comments = None


# --- Test workflows ----------------------------------------------------------

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
    draft = WorkflowState(0, title="Draft", description="Only owner can see it")
    pending = WorkflowState(1, title="Pending", description="Pending review")
    published = WorkflowState(2, title="Published", description="Published")
    withdrawn = WorkflowState(3, title="Withdrawn", description="Withdrawn by owner")
    rejected = WorkflowState(4, title="Rejected", description="Rejected by reviewer")

    # Define a state group
    not_published = WorkflowStateGroup([0, 1], title="Not Published")
    removed = WorkflowStateGroup([withdrawn, rejected], title="Removed")

    def permissions(self):
        """
        Return permissions available to current user. A permission can be any hashable token.
        """
        perms = super(MyDocumentWorkflow, self).permissions()
        if self.context and self.context.get('is_admin'):
            perms = perms + ['can_publish', 'can_return']
        if self.context and self.context.get('is_reviewer'):
            perms = perms + ['can_return']
        return perms

    # Define a transition. There can be multiple transitions connecting any two states.
    # Parameters: newstate, permission, title, description
    @draft.transition(pending, None, title='Submit')
    def submit(self):
        """
        Change workflow state from draft to pending.
        """
        # Do something here
        # ...
        pass  # State will be changed automatically if we don't raise an exception

    @pending.transition(published, 'can_publish', title="Publish")
    def publish(self):
        """
        Publish the document.
        """
        # Also do something here
        # ...
        if not self.document.email_verified:
            raise WorkflowTransitionException("Email address is not verified.")

    @draft.transition(withdrawn, None, title='Withdraw')
    @pending.transition(withdrawn, None, title='Withdraw')
    @published.transition(withdrawn, None, title='Withdraw')
    def withdraw(self):
        """
        Withdraw the document.
        """
        pass  # State will change automatically

    @withdrawn.transition_from([draft, pending, published], None, title='Also Withdraw')
    def also_withdraw(self):
        """
        Withdraw the document.
        """
        pass  # State will change automatically

    @pending.transition(draft, 'can_return', title='Return for review')
    class ReturnForReview(InteractiveTransition):
        def form(self):
            return {'comments': six.string_types}

        def validate(self, form):
            try:
                assert 'comments' in form
                assert isinstance(form['comments'], six.string_types)
            except AssertionError:
                return False
            else:
                return True

        # The submit method gets wrapped by the class decorator
        def submit(self, form):
            self.document.comments = form['comments']
            # State will change automatically when this method returns


class MyDocumentWorkflowExtraState(MyDocumentWorkflow):
    expired = WorkflowState(5, title="Expired")


class MyDocumentWorkflowDict(MyDocumentWorkflow):
    state_attr = None
    state_key = 'status'


class MyDocumentWorkflowCustom(MyDocumentWorkflow):
    state_attr = None

    @classmethod
    def state_get(cls, document):
        """
        Demo state_get method.
        """
        if isinstance(document, dict):
            return document['status']
        else:
            return document.status

    @classmethod
    def state_set(cls, document, value):
        if isinstance(document, dict):
            document['status'] = value
        else:
            document.status = value


class MyDocumentExternalTransitions(DocumentWorkflow):
    """
    Workflow with transitions defined externally.
    """
    state_attr = 'status'

    draft = WorkflowState(0, title="Draft", description="Only owner can see it")
    published = WorkflowState(1, title="Published", description="Published")


@MyDocumentExternalTransitions.draft.transition(MyDocumentExternalTransitions.published, None, title="Publish")
def publish_ext(workflow):
    pass


@MyDocumentExternalTransitions.published.transition(MyDocumentExternalTransitions.draft, None, title="Unpublish")
def unpublish_ext(workflow):
    pass


# -- Tests --------------------------------------------------------------------

class TestWorkflow(unittest.TestCase):
    def test_no_default_state(self):
        doc = MyDocument()
        self.assertRaises(WorkflowStateException, MyDocumentWorkflow, doc)

    def test_empty_document(self):
        class Doc:
            pass
        doc = Doc()
        self.assertRaises(WorkflowStateException, MyDocumentWorkflow, doc)

    def test_state_key_unknown_state(self):
        doc = {}
        self.assertRaises(WorkflowStateException, MyDocumentWorkflowDict, doc)

    def test_states(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        self.assertEqual(wf.state, wf.draft)
        for state in (wf.pending, wf.published, wf.withdrawn, wf.rejected):
            self.assertNotEqual(wf.state, state)

    def test_transition(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        wf.submit()
        self.assertEqual(wf.state, wf.pending)

    def test_transition_signal(self):
        @MyDocumentWorkflow.submit.signal.connect
        def set_signalled(sender):
            self.signalled = sender

        self.signalled = None
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        wf.submit()
        self.assertNotEqual(self.signalled, False)
        self.assertTrue(isinstance(self.signalled, WorkflowTransition))

    def test_transition_list(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        self.assertEqual(len(wf.transitions()), 3)
        self.assertEqual(wf.transitions()['submit'].title, 'Submit')

    def test_invalid_transitions(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        self.assertRaises(WorkflowTransitionException, wf.publish)
        wf.submit()
        self.assertEqual(wf.state, wf.pending)
        self.assertRaises(WorkflowPermissionException, wf.publish)
        wf.context = {'is_admin': True}
        self.assertRaises(WorkflowTransitionException, wf.publish)

    def test_transition_sequence(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc, context={'is_admin': True})
        wf.submit()
        doc.email_verified = True
        wf.publish()
        self.assertEqual(wf.state, wf.published)

    def test_multi_transition(self):
        doc = MyDocument()
        doc.status = MyDocumentWorkflow.draft.value
        wf = MyDocumentWorkflow(doc, context={'is_admin': True})
        self.assertEqual(wf.state, wf.draft)
        wf.withdraw()
        self.assertEqual(wf.state, wf.withdrawn)

        doc.status = MyDocumentWorkflow.pending.value
        self.assertEqual(wf.state, wf.pending)
        wf.withdraw()
        self.assertEqual(wf.state, wf.withdrawn)

        doc.status = MyDocumentWorkflow.published.value
        self.assertEqual(wf.state, wf.published)
        wf.withdraw()
        self.assertEqual(wf.state, wf.withdrawn)

    def transition_from(self):
        doc = MyDocument()
        doc.status = MyDocumentWorkflow.draft.value
        wf = MyDocumentWorkflow(doc, context={'is_admin': True})
        self.assertEqual(wf.state, wf.draft)
        wf.also_withdraw()
        self.assertEqual(wf.state, wf.withdrawn)

    def test_inherited_workflow(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflowExtraState(doc)
        self.assertEqual(len(wf.states()), 6)

    def test_class_statelist(self):
        self.assertEqual(len(MyDocumentWorkflow.states()), 5)
        self.assertEqual(len(MyDocumentWorkflowExtraState.states()), 6)

    def test_state_seq(self):
        self.assertEqual([s.name for s in MyDocumentWorkflow.states()],
                         ['draft', 'pending', 'published', 'withdrawn', 'rejected'])
        self.assertEqual([s.name for s in MyDocumentWorkflowExtraState.states()],
                         ['draft', 'pending', 'published', 'withdrawn', 'rejected', 'expired'])

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

    def test_state_group_with_named_states(self):
        doc = MyDocument()
        doc.status = 3
        wf = MyDocumentWorkflow(doc)
        self.assertEqual(wf.removed(), True)

    def test_repr(self):
        doc = MyDocument()
        doc.status = 0
        wf = MyDocumentWorkflow(doc)
        self.assertEqual(repr(wf.draft), "<WorkflowState 'Draft'>")
        self.assertEqual(repr(wf.not_published), "<WorkflowStateGroup 'Not Published'>")
        self.assertEqual(repr(wf), "<Workflow MyDocumentWorkflow>")

    def test_unattached_workflowstate(self):
        self.assertRaises(WorkflowStateException, MyDocumentWorkflow.draft)
        self.assertRaises(WorkflowStateException, MyDocumentWorkflow.not_published)

    def test_state_key(self):
        doc = {}
        doc['status'] = 0
        wf = MyDocumentWorkflowDict(doc)
        wf.submit()
        self.assertEqual(doc['status'], 1)

    def test_state_custom(self):
        doc1 = MyDocument()
        doc1.status = 0
        wf1 = MyDocumentWorkflowCustom(doc1)
        wf1.submit()
        self.assertEqual(wf1.state, wf1.pending)
        self.assertEqual(doc1.status, wf1.pending.value)

        doc2 = {}
        doc2['status'] = 0
        wf2 = MyDocumentWorkflowCustom(doc2)
        wf2.submit()
        self.assertEqual(wf2.state, wf2.pending)
        self.assertEqual(doc2['status'], wf2.pending.value)

    def test_get_workflow(self):
        MyDocumentWorkflow.apply_on(MyDocument)
        doc = MyDocument()
        doc.status = 0
        self.assertTrue(isinstance(doc.workflow(), MyDocumentWorkflow))
        self.assertRaises(WorkflowException, MyDocumentWorkflow.apply_on, MyDocument)
        self.assertTrue(doc.workflow().draft())
        wf1 = doc.workflow()
        wf2 = doc.workflow()
        self.assertTrue(wf1 is wf2)

    def test_external_transitions(self):
        doc = MyDocument()
        doc.status = 0
        workflow = MyDocumentExternalTransitions(doc)
        self.assertEqual(list(workflow.transitions().keys()), ['publish_ext'])
        publish_ext(workflow)
        self.assertEqual(doc.status, 1)
        self.assertEqual(list(workflow.transitions().keys()), ['unpublish_ext'])

    def test_sort_documents(self):
        doc1 = MyDocument()
        doc1.status = 0
        doc2 = MyDocument()
        doc2.status = 0
        doc3 = MyDocument()
        doc3.status = 1
        self.assertEqual(MyDocumentWorkflow.sort_documents([doc1, doc2, doc3]),
                         {'draft': [doc1, doc2], 'pending': [doc3]})

    def test_interactive_transitions(self):
        doc = MyDocument()
        doc.status = 0  # Draft
        workflow = MyDocumentWorkflow(doc)
        # Raises incorrect state
        self.assertRaises(WorkflowTransitionException, workflow.ReturnForReview)
        doc.status = 1  # Pending
        # Raises incorrect permission
        self.assertRaises(WorkflowPermissionException, workflow.ReturnForReview)
        workflow.context = {'is_reviewer': True}

        # The transition works now. Test its methods
        return_for_review = workflow.ReturnForReview()
        self.assertEqual(return_for_review.form(), {'comments': six.string_types})
        self.assertFalse(return_for_review.validate({}))
        self.assertFalse(return_for_review.validate({'comments': 0}))
        self.assertTrue(return_for_review.validate({'comments': 'test comment'}))

        # For coverage, test repr
        self.assertEqual(repr(return_for_review), '<InteractiveTransition ReturnForReview>')

        # Submit the transition (part 1, pre submit status)
        self.assertEqual(doc.status, 1)
        self.assertEqual(doc.comments, None)
        # Submit the transition (part 2, post submit status)
        return_for_review.submit({'comments': 'test comment'})
        self.assertEqual(doc.status, 0)
        self.assertEqual(doc.comments, 'test comment')

    def test_clobber_workflow_class(self):
        """
        Instantiating a workflow does not clobber the workflow class.
        """
        for state in MyDocumentWorkflow._states.values():
            self.assertTrue(state._parent is None)

        doc = MyDocument()
        doc.status = 0
        workflow = MyDocumentWorkflow(doc)

        for state in MyDocumentWorkflow._states.values():
            self.assertTrue(state._parent is None)

        for state in workflow._states.values():
            self.assertFalse(state._parent is None)


if __name__ == '__main__':
    unittest.main()
