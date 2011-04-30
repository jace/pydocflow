# -*- coding: utf-8 -*-

from functools import wraps

class WorkflowException(Exception):
    pass

class WorkflowStateException(WorkflowException):
    pass

class WorkflowTransitionException(WorkflowException):
    pass

class WorkflowPermissionException(WorkflowException):
    pass


class WorkflowState(object):
    def __init__(self, value, title=u'', description=u''):
        self.value = value
        self.name = None # Not named yet
        self.title = title
        self.description = description
        self._parent = None

    def attach(self, workflow):
        newstate = self.__class__(self.value, self.title, self.description)
        newstate.name = self.name
        newstate._parent = workflow
        return newstate

    def __repr__(self):
        return "<WorkflowState %s>" % repr(self.title)

    def __call__(self):
        if not self._parent:
            raise WorkflowStateException("Unattached state")
        return self._parent._getStateValue() == self.value

    def __eq__(self, other):
        return (self.value == other.value and
                self.name == other.name and
                self.title == other.title and
                self.description == other.description)

    def __ne__(self, other):
        return not self.__eq__(other)

    def transition(self, tostate, permission, title='', description=''):
        """
        Decorator for transition functions.
        """
        def inner(f):
            # TODO: Save to list of transitions here
            @wraps(f)
            def decorated_function(workflow, context=None, *args, **kwargs):
                # Perform tests: is state correct? Is permission available?
                if workflow.state != self:
                    raise WorkflowTransitionException("Incorrect state")
                if permission and permission not in workflow.permissions(context):
                    raise WorkflowPermissionException("Permission not available")
                result = f(workflow, context, *args, **kwargs)
                workflow._setStateValue(tostate.value)
                return result
            return decorated_function
        return inner

class WorkflowStateGroup(WorkflowState):
    def __repr__(self):
        return '<WorklowStateGroup %s>' % repr(self.title)

    def __call__(self):
        if not self._parent:
            raise WorkflowStateException("Unattached state")
        return self._parent._getStateValue() in self.value


class _InitDocumentWorkflow(type):
    def __new__(cls, name, bases, attrs):
        attrs['_is_document_workflow'] = True
        attrs['_name'] = name
        attrs['_states'] = {} # state_name: object
        attrs['_state_groups'] = {} # state_group: object
        attrs['_state_values'] = {} # Reverse lookup: value to object
        # If any base class contains _states, _state_groups or _state_values, extend them
        for base in bases:
            if hasattr(base, '_is_document_workflow') and base._is_document_workflow:
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

        return super(_InitDocumentWorkflow, cls).__new__(cls, name, bases, attrs)


class DocumentWorkflow(object):
    __metaclass__ = _InitDocumentWorkflow

    #: State is contained in an attribute on the document
    state_attr = None
    #: Or, state is contained in a key in the document
    state_key = None
    #: Or, state is retrieved or set via special methods.
    #: state_get accepts a document as parameter, and state_set
    #: takes a document and a value
    state_get = None
    state_set = None

    def __init__(self, document):
        self._document = document
        self._state = None # No default state yet
        state = self._getStateValue()
        if state not in self._state_values:
            raise WorkflowStateException("Unknown state")
        # Attach states to self. Make copy and iterate:
        # This code is used just to make it possible to test
        # if a state is active by calling it: workflow.draft(), etc
        for statename, stateob in list(self._states.items()):
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

    def _getStateValue(self):
        # Get the state value from document
        if self.state_attr:
            return getattr(self._document, self.state_attr)
        elif self.state_key:
            return self.document[self.state_key]
        elif self.state_get:
            return self.state_get(self._document)
        else:
            raise WorkflowStateException("State cannot be read")

    def _setStateValue(self, value):
        # Set state value on document
        if self.state_attr:
            setattr(self._document, self.state_attr, value)
        elif self.state_key:
            self._document[self.state_key] = value
        elif self.state_set:
            self.state_set(self._document, value)
        else:
            raise WorkflowStateException("State cannot be changed")

    @property
    def state(self):
        return self._state_values[self._getStateValue()]

    #@state.setter
    #def state(self, value):
    #    if not isinstance(value, WorkflowState):
    #        raise WorkflowStateException("Not a state")
    #    self._setStateValue(value.value)

    def all_states(self):
        """
        All states
        """
        return dict(self._states) # Make a shallow copy

    def permissions(self, context=None):
        """
        Permissions available in given context.
        """
        return []

    def transitions(self, context=None):
        pass
