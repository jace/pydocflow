# -*- coding: utf-8 -*-

"""
Docflow: Python Document Workflows
"""

import six
from functools import wraps
import weakref
from types import MethodType
try:
    from collections import OrderedDict
except ImportError:  # pragma: no cover
    from ordereddict import OrderedDict

try:
    from blinker import Signal
except ImportError:
    Signal = None

from ._version import __version__  # NOQA

__all__ = ['DocumentWorkflow', 'WorkflowState', 'WorkflowStateGroup', 'InteractiveTransition']


class WorkflowException(Exception):
    pass


class WorkflowStateException(WorkflowException):
    pass


class WorkflowTransitionException(WorkflowException):
    pass


class WorkflowPermissionException(WorkflowException):
    pass


_creation_order = 1


def _set_creation_order(instance):
    """
    Assign a '_creation_order' sequence to the given instance.

    This allows multiple instances to be sorted in order of creation
    (typically within a single thread; the counter is not threadsafe).

    This code is from SQLAlchemy, available here:
    https://github.com/zzzeek/sqlalchemy/blob/e45e4aa97d96421173da19d63f433795dad6e4e9/lib/sqlalchemy/util/langhelpers.py#L1224-L1237

    Only recommended for use at app load time.
    """
    global _creation_order
    instance._creation_order = _creation_order
    _creation_order += 1


class WorkflowTransition(object):
    """
    Transition between states.
    """
    def __init__(self, name,
                 title='',
                 description='',
                 category='',
                 permission='',
                 state_from=None,
                 state_to=None,
                 **kwargs):
        self.name = name
        self.title = title
        self.description = description
        self.category = category
        self.permission = permission
        self.state_from = weakref.ref(state_from)
        self.state_to = weakref.ref(state_to)
        self.__dict__.update(kwargs)


class InteractiveTransition(object):
    """
    Multipart workflow transitions. Subclasses of this class may provide
    methods to return a form, validate the form and submit the form.
    Implementing a :meth:`submit` method is mandatory. :meth:`submit`
    will be wrapped by the :meth:`~WorkflowState.transition` decorator to
    automatically update the document's state value.

    Instances of :class:`InteractiveTransition` will receive
    :attr:`workflow` and :attr:`document` attributes pointing to the workflow
    instance and document respectively.
    """
    def __init__(self, workflow):
        self.workflow = workflow
        self.document = workflow.document

    def __repr__(self):
        return '<InteractiveTransition %s>' % self.__class__.__name__

    def submit(self):  # pragma: no cover
        """
        InteractiveTransition subclasses must override this method. If this
        method returns without raising an exception, the document's state
        will be updated automatically.
        """
        raise NotImplementedError


class WorkflowState(object):
    """
    State in a workflow.
    """

    exception_state = WorkflowStateException
    exception_transition = WorkflowTransitionException
    exception_permission = WorkflowPermissionException

    def __init__(self, value, title=u'', description=u''):
        self.value = value
        self.values = [value]
        self.name = None  # Not named yet
        self.title = title
        self.description = description
        self._parent = None
        self._transitions = OrderedDict()

        _set_creation_order(self)

    def attach(self, workflow):
        """
        Attach this workflow state to a workflow instance.
        """
        # Attaching works by creating a new copy of the state with _parent
        # now referring to the workflow instance.
        newstate = self.__class__(self.value, self.title, self.description)
        newstate.name = self.name
        newstate._parent = weakref.ref(workflow)
        newstate._transitions = self._transitions
        return newstate

    def __repr__(self):
        return "<WorkflowState %s>" % repr(self.title)

    def __call__(self):
        if self._parent is None or self._parent() is None:
            raise self.exception_state("Unattached state")
        return self._parent()._getStateValue() == self.value

    def __eq__(self, other):
        return isinstance(other, WorkflowState) and self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def transition(self, state_to, permission,
                   name=None, title='', description='', category='', **kw):
        """
        Decorator for transition functions.
        """
        def inner(f):
            if hasattr(f, '_workflow_transition_inner'):
                f = f._workflow_transition_inner

            workflow_name = name or f.__name__

            @wraps(f)
            def decorated_function(workflow, *args, **kwargs):
                # Perform tests: is state correct? Is permission available?
                if workflow_name not in workflow.state._transitions:
                    raise self.exception_transition("Incorrect state")
                t = workflow.state._transitions[workflow_name]
                if t.permission and (t.permission not in workflow.permissions()):
                    raise self.exception_permission(
                        "Permission not available")
                result = f(workflow, *args, **kwargs)
                if isinstance(result, InteractiveTransition):
                    @wraps(f.submit)
                    def workflow_submit(self, *args, **kwargs):
                        r = f.submit(self, *args, **kwargs)
                        workflow._setStateValue(t.state_to().value)
                        if t.signal is not None:
                            t.signal.send(t)
                        return r
                    if six.PY3:  # pragma: no cover
                        result.submit = MethodType(workflow_submit, result)
                    else:
                        result.submit = MethodType(workflow_submit, result, f)
                else:
                    workflow._setStateValue(t.state_to().value)
                    if t.signal is not None:
                        t.signal.send(t)

                return result

            t = WorkflowTransition(name=workflow_name,
                                   title=title,
                                   description=description,
                                   category=category,
                                   permission=permission,
                                   state_from=self,
                                   state_to=state_to,
                                   **kw)
            self._transitions[workflow_name] = t
            decorated_function._workflow_transition_inner = f
            if Signal is not None:
                if not hasattr(decorated_function, 'signal'):
                    decorated_function.signal = Signal()
            else:
                decorated_function.signal = None
            t.signal = decorated_function.signal
            return decorated_function
        return inner

    def transition_from(self, state_from, permission, **kwargs):
        """
        The reverse of :meth:`WorkflowState.transition`, specifies a transition to this
        state from one or more source states. Does not accept WorkflowStateGroup.
        """
        def inner(f):
            states = [state_from] if isinstance(state_from, WorkflowState) else state_from
            for state in states:
                return state.transition(self, permission, **kwargs)(f)
        return inner


class WorkflowStateGroup(WorkflowState):
    """
    Group of states in a workflow. The value parameter is a list of values
    or WorklowState instances.
    """
    def __init__(self, value, title=u'', description=u''):
        # Convert all WorkflowState instances to values
        value = [item.value if isinstance(item, WorkflowState) else item for item in value]
        super(WorkflowStateGroup, self).__init__(value, title, description)
        self.values = tuple(value)

    def __repr__(self):
        return '<WorkflowStateGroup %s>' % repr(self.title)

    def __call__(self):
        if self._parent is None or self._parent() is None:
            raise self.exception_state("Unattached state")
        return self._parent()._getStateValue() in self.value

    def transition(self, *args, **kwargs):
        raise SyntaxError("WorkflowStateGroups cannot have transitions")


class _InitDocumentWorkflow(type):
    def __new__(cls, name, bases, attrs):
        attrs['_is_document_workflow'] = True
        attrs['_name'] = name
        attrs['_states'] = {}  # state_name: object
        attrs['_state_groups'] = {}  # state_group: object
        attrs['_state_values'] = {}  # Reverse lookup: value to object
        # If any base class contains _states, _state_groups or _state_values,
        # extend them
        for base in bases:
            if hasattr(base,
                       '_is_document_workflow') and base._is_document_workflow:
                attrs['_states'].update(base._states)
                attrs['_state_groups'].update(base._state_groups)
                attrs['_state_values'].update(base._state_values)

        for statename, stateob in attrs.items():
            if isinstance(stateob, WorkflowState):
                stateob.name = statename
                if isinstance(stateob, WorkflowStateGroup):
                    attrs['_state_groups'][statename] = stateob
                else:
                    attrs['_states'][statename] = stateob
                    # A group doesn't have a single value, so don't add groups
                    attrs['_state_values'][stateob.value] = stateob

        attrs['_states_sorted'] = sorted(attrs['_states'].values(),
                                         key=lambda s: s._creation_order)
        return super(_InitDocumentWorkflow, cls).__new__(
            cls, name, bases, attrs)


class DocumentWorkflow(six.with_metaclass(_InitDocumentWorkflow)):
    """
    Base class for document workflows.
    """

    #: Subclasses may override the exception that is raised
    exception_state = WorkflowStateException

    #: The name of this workflow (for when documents can have multiple workflows)
    name = None

    #: One of these attributes must be overridden by subclasses

    #: State is contained in an attribute on the document
    state_attr = None
    #: Or, state is contained in a key in the document
    state_key = None
    #: Or, state is retrieved or set via special methods.
    #: state_get accepts a document as parameter, and state_set
    #: takes a document and a value
    state_get = None
    state_set = None

    def __init__(self, document, context=None):
        self.document = document
        self.context = context
        self._state = None  # No default state yet
        state = self._getStateValue()
        if state not in self._state_values:
            raise self.exception_state("Unknown state")
        # Attach states to self. Make copy and iterate:
        # This code is used just to make it possible to test
        # if a state is active by calling it: workflow.draft(), etc
        class_states = list(self._states.items())  # Copy states from the class
        self._states = {}  # Replace _states in the instance with attached states
        for statename, stateob in class_states:
            attached = stateob.attach(self)
            setattr(self, statename, attached)
            self._states[statename] = attached
            self._state_values[attached.value] = attached
        for statename, stateob in list(self._state_groups.items()):
            attached = stateob.attach(self)
            setattr(self, statename, attached)
            self._state_groups[statename] = attached

    def __repr__(self):
        return '<Workflow %s>' % self._name

    @classmethod
    def _getStateValueInner(cls, document):
        # Get the state value from document
        if cls.state_attr:
            try:
                return getattr(document, cls.state_attr)
            except AttributeError:
                raise cls.exception_state("Unknown state")
        elif cls.state_key:
            try:
                return document[cls.state_key]
            except:
                raise cls.exception_state("Unknown state")
        elif cls.state_get:
            return cls.state_get(document)
        else:  # pragma: no cover
            raise cls.exception_state("State cannot be read")

    def _getStateValue(self):
        return self._getStateValueInner(self.document)

    def _setStateValue(self, value):
        # Set state value on document
        if self.state_attr:
            setattr(self.document, self.state_attr, value)
        elif self.state_key:
            self.document[self.state_key] = value
        elif self.state_set:
            self.state_set(self.document, value)
        else:  # pragma: no cover
            raise self.exception_state("State cannot be changed")

    @property
    def state(self):
        return self._state_values[self._getStateValue()]

    @classmethod
    def states(cls):
        """
        All states, sorted.
        """
        return list(cls._states_sorted)  # Make a shallow copy

    def permissions(self):
        """
        Permissions available in the current context. This method must be
        overridden by subclasses. Context is available as self.context,
        set when the workflow was initialized for the document. It is not
        passed as a parameter to this method.
        """
        return []

    def transitions(self):
        """
        Transitions available in the current state and context.
        """
        permissions = self.permissions()
        result = OrderedDict()
        for k, v in self.state._transitions.items():
            if v.permission is None or v.permission in permissions:
                result[k] = v
        return result

    @classmethod
    def apply_on(cls, docclass):
        """Apply workflow on specified document class."""
        def workflow(self, name=None):
            """Return a workflow wrapper for this document."""
            if not hasattr(self, '_workflow_instances'):
                self._workflow_instances = {}
            # Workflows can be re-instantiated anytime because they don't store
            # any data. All storage is in the document. However, there is a small
            # time cost to instantiation, so we cache when we can.
            if name not in self._workflow_instances:
                self._workflow_instances[name] = self._workflows[name](self)
            return self._workflow_instances[name]

        if not hasattr(docclass, '_workflows'):
            docclass._workflows = {}
        if cls.name in docclass._workflows:
            raise WorkflowException(
                u"This document class already has a workflow named {name}".format(name=repr(cls.name)))
        docclass._workflows[cls.name] = cls
        if not hasattr(docclass, 'workflow'):
            docclass.workflow = workflow

    @classmethod
    def sort_documents(cls, documents):
        """
        Sort the given collection of documents by workflow state.
        Returns a dictionary of lists.
        """
        result = {}
        for doc in documents:
            state = cls._state_values[cls._getStateValueInner(doc)]
            result.setdefault(state.name, []).append(doc)
        return result
