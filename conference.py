#!/usr/bin/env python

"""
conference.py --  conference server-side Python App Engine API;
    uses Google Cloud Endpoints

"""
import json
import os
import time
import logging

from datetime import datetime
import time

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import BooleanMessage
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import WishlistForm
from models import WishlistForms
from models import Wishlist
from models import WishlistQuery
from models import WishlistSpeakerQuery
from models import WishlistTypeQuery
from models import TeeShirtSize
from models import StringMessage
from models import Session 
from models import SessionForm
from models import SessionForms
from models import SessionQuery
from models import SessionQueryType
from models import SessionQuerySpeaker




from utils import getUserId

from settings import WEB_CLIENT_ID

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"
ANNOUNCEMENT_TPL = ('Last chance to attend! The following conferences '
                    'are nearly sold out: %s')

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": [ "Default", "Topic" ],
}

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'CITY': 'city',
            'TOPIC': 'topics',
            'MONTH': 'month',
            'MAX_ATTENDEES': 'maxAttendees',
            }

S_DEFAULTS = {
    "typeOfSession": ["Workshop", "Lecture"],
}

CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)

CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)



# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='conference', version='v1', 
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

# - - - Conference objects - - - - - - - - - - - - - - - - -

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf


    def _createConferenceObject(self, request):
        """Create or update Conference object, returning ConferenceForm/request."""
        # preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Conference 'name' field required")

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeKey']
        del data['organizerDisplayName']

        # add default values for those missing (both data model & outbound Message)
        for df in DEFAULTS:
            if data[df] in (None, []):
                data[df] = DEFAULTS[df]
                setattr(request, df, DEFAULTS[df])

        # convert dates from strings to Date objects; set month based on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(data['endDate'][:10], "%Y-%m-%d").date()

        # set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # generate Profile Key based on user ID and Conference
        # ID based on Profile key get Conference key from ID
        p_key = ndb.Key(Profile, user_id)
        c_id = Conference.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Conference, c_id, parent=p_key)
        data['key'] = c_key
        data['organizerUserId'] = request.organizerUserId = user_id

        # create Conference, send email to organizer confirming
        # creation of Conference & return (modified) ConferenceForm
        Conference(**data).put()
        # TODO 2: add confirmation email sending task to queue
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )

        return request


    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        # copy ConferenceForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)

        # check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)


    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference w/provided fields & return w/updated info."""
        return self._updateConferenceObject(request)


    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % request.websafeConferenceKey)
        prof = conf.key.parent().get()
        # return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id =  getUserId(user)
        # create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[self._copyConferenceToForm(conf, getattr(prof, 'displayName')) for conf in confs]
        )


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)

        # need to fetch organiser displayName from profiles
        # get all keys and use get_multi for speed
        organisers = [(ndb.Key(Profile, conf.organizerUserId)) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ConferenceForm object per Conference
        return ConferenceForms(
                items=[self._copyConferenceToForm(conf, names[conf.organizerUserId]) for conf in \
                conferences]
        )


# - - - Session objects - - - - - - - - - - - - - - - - -
    def _transferSessionToForm(self, sesh):
        """get fields required into SessionForm from Session"""
        seshForm = SessionForm()

        for field in seshForm.all_fields():
            if hasattr(sesh, field.name):
                if field.name.endswith('date') or field.name.endswith('Time'):
                    setattr(seshForm, field.name, str(getattr(sesh, field.name)))
                else:
                    setattr(seshForm, field.name, getattr(sesh, field.name))
        seshForm.check_initialized()

        return seshForm

    def _createSessionObject(self, request):
        """Create Session object, returning SessionForm/request."""
        # check auth
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # copy SessionForm into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        user_id = getUserId(user)
        conf = ndb.Key(urlsafe=data['confwebsafeKey']).get()

        if not request.name:
            raise endpoints.BadRequestException("Session 'name' field required")


        # add default values for those missing (both data model & outbound Message)
        for df in S_DEFAULTS:
            if data[df] in (None, []):
                data[df] = S_DEFAULTS[df]
                setattr(request, df, S_DEFAULTS[df])

        # add date and time
        if data['startTime']:
            data['startTime'] = datetime.strptime(data['startTime'], "%H:%M").time()
        if data['date']:
            data['date'] = datetime.strptime(data['date'][:10], "%Y-%m-%d").date()

        # generate session key from conference key
        p_key = conf.key
        c_id = Session.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Session, c_id, parent=p_key)
        data['key'] = c_key
        if not data['speaker']:
            data['speaker'] = user.nickname()
        del data['confwebsafeKey']

        # if speaker has more than 1 session, add to featured speaker memcache
        q = Session.query().filter(Session.speaker == data['speaker']).count()
        if q > 1:
            taskqueue.add(params={'speaker': data['speaker']}, url='/tasks/set_featured_speaker')

        Session(**data).put()
        return request

# - - - Sessions - - - - - - - - - - - - - - - - - - - -
    @endpoints.method(SessionForm, SessionForm, path='session',
            http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session. open only to the organizer of the conference"""
        return self._createSessionObject(request)

    @endpoints.method(endpoints.ResourceContainer(
        speaker=messages.StringField(1)), SessionForms,
            path='session/{speaker}',
            http_method='GET', name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Given a speaker, return all sessions given by this particular speaker, across all conferences"""
        # query session
        q = Session.query()

        #filter by speaker
        q = Session.query(Session.speaker == request.speaker)

        return SessionForms(
            items=[self._transferSessionToForm(sesh) for sesh in q]
        )


    @endpoints.method(SessionQueryType, SessionForms, path='queryType',
            http_method='GET', name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Get session by typeOfSession."""
        if not request.websafeConferenceKey:
            raise endpoints.ForbiddenException('websafeConferenceKey is required.')

        if not request.typeOfSession:
            raise endpoints.ForbiddenException('typeOfSession is required.')

        #parent key
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()

        # filter by typeOfSession after querying session by ancestor
        q = Session.query(ancestor=conf.key).filter(Session.typeOfSession == request.typeOfSession)

        return SessionForms(items=[self._transferSessionToForm(sesh) for sesh in q])

    @endpoints.method(SessionQuery, SessionForms, path="sessionQuery",
            http_method="GET", name="getConferenceSessions")
    def getConferenceSessions(self, request):
        """Returns sessions of a given conference"""
        if not request.websafeConferenceKey:
            raise endpoints.ForbiddenException("websafeConferenceKey is required.")

        #parent key
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()

        #ancestral session query
        q = Session.query(ancestor=conf.key).fetch()
        return SessionForms(items=[self._transferSessionToForm(sesh) for sesh in q])


#----------Wish List object---------------------------------------

    def _copyWishlistToForm(self, wish):
        """Copy relevant fields from Wishlist to WishlistForm."""
        wishForm = WishlistForm()
        wishForm.sessionName = wish.sessionName
        wishForm.sessionKey = str(wish.sessionKey)
        wishFormtypeOfSession = wish.typeOfSession
        wishForm.check_initialized()
        return wishForm

    def _createWishlistObject(self, request):
        """Create or update Wishlist object, returning WishlistForm/request."""

        # check auth
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        # check sessionName exists
        if not request.sessionName:
            raise endpoints.UnauthorizedException('Name required')
        # get userId
        user_id = getUserId(user)

        # get session key
        this_session = Session.query(Session.name == request.sessionName).get()

        # populate dict
        data = {'userId': user_id, 'sessionName': request.sessionName, 'sessionKey': this_session.key,
                'typeOfSession': this_session.typeOfSession}

        # generate wishlist key from session key
        p_key = this_session.key
        c_id = Wishlist.allocate_ids(size=1, parent=p_key)[0]
        c_key = ndb.Key(Wishlist, c_id, parent=p_key)
        data['key'] = c_key

        # query wishlist, filter by userId and sessionName, then count
        q = Wishlist.query()
        q = q.filter(Wishlist.userId == user_id)

        # if this session already in user's wishlist, bounce
        for i in q:
            if i.sessionKey == this_session.key:
                raise endpoints.UnauthorizedException('Session  added to wishlist already')

        # save to wishlist
        Wishlist(**data).put()
        return request


#--------Sessions to User WishList--------------------------------------
    @endpoints.method(WishlistForm, WishlistForm, path='wishlist',
            http_method='POST', name='addSessionToWishlist')
    def addSessionToWishlist(self, request):
        """dds the session to the user's list of sessions they are interested in attending"""
        return self._createWishlistObject(request)

    @endpoints.method(message_types.VoidMessage, WishlistForms, path='wishlistQuery',
            http_method='GET', name='getSessionsInWishlist')
    def getSessionsInWishlist(self, request):
        """return a user's wishlist."""

        # check auth
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        # get userId
        user_id = getUserId(user)
        # query wishlist, filter by userId
        q = Wishlist.query().filter(Wishlist.userId == user_id)

        return WishlistForms(items=[self._copyWishlistToForm(wish) for wish in q])


#-----Two Additional Queries------------------------------------
    @endpoints.method(WishlistTypeQuery, WishlistForms, path='wishlistTypeQuery',
            http_method='GET', name='returnWishlistType')
    def returnWishlistType(self, request):
        """Return whislist by type."""

        # check authentication
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # acquire userId
        user_id = getUserId(user)

        # query wishlist, filter by userId and typeOfSession
        q = Wishlist.query()
        q = q.filter(Wishlist.userId == user_id)
        q = q.filter(Wishlist.typeOfSession == request.typeOfSession)

        return WishlistForms(items=[self._copyWishlistToForm(wish) for wish in q])

    @endpoints.method(WishlistSpeakerQuery, WishlistForms, path='wishlistSpeakerQuery',
            http_method='GET', name='returnWishlistSpeaker')
    def returnWishlistSpeaker(self, request):
        """Given a speaker, return the wishlist by the speaker."""

        # verify authentication
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # obtain userId
        user_id = getUserId(user)

        # query session, filter by speaker
        q = Session.query().filter(Session.speaker == request.speaker)

        # query wishlist, filter by userId
        p = Wishlist.query().filter(Wishlist.userId == user_id)

        a = []
        for s in q:
            for w in p:
                if s.key == w.sessionKey:
                    a.append(w)

        return WishlistForms(items=[self._copyWishlistToForm(wish) for wish in a])


# - - - Profile objects - - - - - - - - - - - - - - - - - - -

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        # copy relevant fields from Profile to ProfileForm
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name, getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf


    def _getProfileFromUser(self):
        """Return user Profile from datastore, creating new one if non-existent."""
        # make sure user is authed
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Profile from datastore
        user_id = getUserId(user)
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()

        return profile      # return Profile


    def _doProfile(self, save_request=None):
        """Get user Profile and return to user, possibly updating it first."""
        # get user Profile
        prof = self._getProfileFromUser()

        # if saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(prof, field, str(val))
                        #if field == 'teeShirtSize':
                        #    setattr(prof, field, str(val).upper())
                        #else:
                        #    setattr(prof, field, val)
            prof.put()

        # return ProfileForm
        return self._copyProfileToForm(prof)


    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()


    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update & return user profile."""
        return self._doProfile(request)

# - - - Memecache Announcements - - - - - - - - - - - - - - - - - - - -

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])

        if confs:
            # If there are almost sold out conferences,
            # format announcement and set it in memcache
            announcement = ANNOUNCEMENT_TPL % (
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)

        return announcement


    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        announcement =memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) 
        if not announcement:
            announcement = ""
        return StringMessage(data=announcement)

# - - - Registration - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        prof = self._getProfileFromUser() # get user Profile

        # check if conf exists given websafeConfKey
        # get conference; check that it exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)

        # register
        if reg:
            # check if user already registered otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference")

            # check if seats avail
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")

            # register user, take away one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True

        # unregister
        else:
            # check if user already registered
            if wsck in prof.conferenceKeysToAttend:

                # unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False

        # write things back to the datastore & return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)


    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences that user has registered for."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend]
        conferences = ndb.get_multi(conf_keys)

        # get organizers
        organisers = [ndb.Key(Profile, conf.organizerUserId) for conf in conferences]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return set of ConferenceForm objects per Conference
        return ConferenceForms(items=[self._copyConferenceToForm(conf, names[conf.organizerUserId])\
         for conf in conferences]
        )


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)


    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)



#----------QueryProblem---------------------------
    @endpoints.method(SessionQuery, SessionForms, path='sessionProblemQuery',
            http_method='GET', name='problematicQuery')
    def problematicQuery(self, request):
        """Handle query for all non-workshop sessions before 7 pm."""

        if not request.websafeConferenceKey:
            raise endpoints.ForbiddenException('Requires websafeConferenceKey.')

        #24hr format
        time_is_now = datetime.strptime('19:00:00', "%H:%M:%S").time()
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()

        query_sesh = Session.query(ancestor=conf.key).\
            filter(Session.startTime <= time_is_now)

        list_loader = []
        for stuff in query_sesh:
            if "Workshop" not in stuff.typeOfSession:
                list_loader.append(stuff)

        return SessionForms(items=[self._transferSessionToForm(sesh) for sesh in list_loader])





api = endpoints.api_server([ConferenceApi]) # register API