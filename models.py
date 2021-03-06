#!/usr/bin/env python

"""models.py

"""

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb



class Profile(ndb.Model):
    """Profile -- User profile object"""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)


class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)

class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT


class ProfileMiniForm(messages.Message):
    """ProfileMiniForm -- update Profile form message"""
    displayName = messages.StringField(1)
    teeShirtSize = messages.EnumField('TeeShirtSize', 2)


class ProfileForm(messages.Message):
    """ProfileForm -- Profile outbound form message"""
    displayName = messages.StringField(1)
    mainEmail = messages.StringField(2)
    teeShirtSize = messages.EnumField('TeeShirtSize', 3)


class Conference(ndb.Model):
    """Conference -- Conference object"""
    name            = ndb.StringProperty(required=True)
    description     = ndb.StringProperty()
    organizerUserId = ndb.StringProperty()
    topics          = ndb.StringProperty(repeated=True)
    city            = ndb.StringProperty()
    startDate       = ndb.DateProperty()
    month           = ndb.IntegerProperty()
    endDate         = ndb.DateProperty()
    maxAttendees    = ndb.IntegerProperty()
    seatsAvailable  = ndb.IntegerProperty()

class ConferenceForm(messages.Message):
    """ConferenceForm -- Conference outbound form message"""
    name            = messages.StringField(1)
    description     = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics          = messages.StringField(4, repeated=True)
    city            = messages.StringField(5)
    startDate       = messages.StringField(6)
    month           = messages.IntegerField(7)
    maxAttendees    = messages.IntegerField(8)
    seatsAvailable  = messages.IntegerField(9)
    endDate         = messages.StringField(10)
    websafeKey      = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)


class ConferenceForms(messages.Message):
    """ConferenceForms -- multiple Conference outbound form message"""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)

class ConferenceQueryForm(messages.Message):
    """ConferenceQueryForm -- Conference query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)

class ConferenceQueryForms(messages.Message):
    """ConferenceQueryForms -- multiple ConferenceQueryForm inbound form message"""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)


class Session(ndb.Model):
    """Session ---- Session object"""
    highlights = ndb.StringProperty()
    speaker = ndb.StringProperty()
    duration  = ndb.IntegerProperty()
    date = ndb.DateProperty()
    startTime = ndb.TimeProperty()
    typeOfSession = ndb.StringProperty(repeated=True)
    name = ndb.StringProperty(required=True)
    

class SessionForm(messages.Message):
    """Session Form -- form message outbound"""
    speaker = messages.StringField(3)
    typeOfSession          = messages.StringField(4, repeated=True)
    duration            = messages.IntegerField(5)
    date       = messages.StringField(6)
    startTime           = messages.StringField(7)
    confwebsafeKey      = messages.StringField(8)
    name            = messages.StringField(1)
    highlights     = messages.StringField(2)


class SessionForms(messages.Message):
    """SessionForms multiples outbound"""
    items = messages.MessageField(SessionForm, 1, repeated=True)

class SessionQuery(messages.Message):
    """ Session query inbound form message"""
    websafeConferenceKey = messages.StringField(1)

class SessionQuerySpeaker(messages.Message):
    """Session query inbound form message"""
    speaker = messages.StringField(1)

class SessionQueryType(messages.Message):
    """Session query inbound form message"""
    typeOfSession = messages.StringField(1)
    websafeConferenceKey = messages.StringField(2)

class Wishlist(ndb.Model):
    """Wishlist -- Wishlist object"""
    sessionName            = ndb.StringProperty(required=True)
    userId            = ndb.StringProperty()
    sessionKey          = ndb.KeyProperty()
    typeOfSession            = ndb.StringProperty(repeated=True)

class WishlistForm(messages.Message):
    """WishlistForm -- Wishlist outbound form message"""
    sessionName          = messages.StringField(1)
    userId            = messages.StringField(2)
    sessionKey          = messages.StringField(3)
    typeOfSession          = messages.StringField(4, repeated=True)

class WishlistForms(messages.Message):
    """WishlistForms -- multiple Wishlist outbound form message"""
    items = messages.MessageField(WishlistForm, 1, repeated=True)

class WishlistQuery(messages.Message):
    """WishlistQueryForm -- WishlistQuery inbound form message"""
    userId = messages.StringField(1)

class WishlistSpeakerQuery(messages.Message):
    """WishlistQueryForm -- WishlistQuery inbound form message"""
    speaker = messages.StringField(1)

class WishlistTypeQuery(messages.Message):
    """WishlistQueryForm -- WishlistQuery inbound form message"""
    typeOfSession = messages.StringField(1)

class TeeShirtSize(messages.Enum):
    """TeeShirtSize -- t-shirt size enumeration value"""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15