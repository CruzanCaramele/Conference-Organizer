**Visit the application at this [link][7]**

## Products
- [App Engine][1]

## Language
- [Python][2]

## APIs
- [Google Cloud Endpoints][3]

## Setup Instructions
1. Update the value of `application` in `app.yaml` to the app ID you
   have registered in the App Engine admin console and would like to use to host
   your instance of this sample.
1. Update the values at the top of `settings.py` to
   reflect the respective client IDs you have registered in the
   [Developer Console][4].
1. Update the value of CLIENT_ID in `static/js/app.js` to the Web client ID
1. (Optional) Mark the configuration files as unchanged as follows:
   `$ git update-index --assume-unchanged app.yaml settings.py static/js/app.js`
1. Run the app with the devserver using `dev_appserver.py DIR`, and ensure it's running by visiting
   your local server's address (by default [localhost:8080][5].)
1. Generate your client library(ies) with [the endpoints tool][6].
1. Deploy your application.


[1]: https://developers.google.com/appengine
[2]: http://python.org
[3]: https://developers.google.com/appengine/docs/python/endpoints/
[4]: https://console.developers.google.com/
[5]: https://localhost:8080/
[6]: https://developers.google.com/appengine/docs/python/endpoints/endpoints_tool
[7]: https://amiable-hour-95808.appspot.com 



## Session Design Choices
- In this design, Profile is an ancestor of both Sessions and Conference.
- A **Session** is a child of Conference, querying by ancestor is then made possible to get all child elements. 
- Within the **Session** model, **speaker** is defined as a string to simplify filtering.
- **typeOfSession** was defined in the model as a repeated property.This allows for multiple session types. 
- **startTime** was defined as a **TimeProperty** instead of **DateProperty** to keep entries to 24 hour time and allow for proper filtering.

## Sessions to User Wishlist
This is to enable users mark some sessions that they are interested in and retrieve their own current wishlist.
- **addSessionToWishlist** :adds the session to the user's list of sessions they are interested in attending
- **getSessionsInWishlist**: return a user's wishlist.

## Two Additional Queries
**returnWishlistType**
- This query returns all sessions on a user's wishlist of a certain type. 
- Useful when a user has been to a few presentations and wanted to attend only workshops for the rest of the day.

**returnWishlistSpeaker**
- Given a user's wishlist, this query will return sessions by the same speaker.
- this allows users to see more sessions from a specific speaker that they have already seen in the past which they like.

## Query Problem
The problem with trying to query for sessions that are both before 7pm and are not workshops is that the app engine does not allow for two inequality filters to be applied to two seperate properties in one query. In getConferenceSessionsProblem, at first I queried only for sessions before 7pm and then tried to delete results that weren't workshops, but the Query object doesn't allow for deletion. Ultimately I iterated over the time query results and used - 'workshop' not in - to find the results I actually wanted and pass them to a new array

- Keeping in mind that the google app engine forbids 2 inequality filters to be implemented to 2 different properties in a single query, this causes a problem in attempting to query for sessions that are not workshops and before 7pm.
- I created the **problematicQuery** method to handle this problem by first querying for sessions that occur before 7pm in ** query_sesh = Session.query(ancestor=conf.key).filter(Session.startTime <= time_is_now**
- I then used a for loop to iterate over the **query_sesh**,  then check if **Workshop** is not found .
- Whenever **Workshop** is not found, the result is appended to an empty list as in ** list_loader.append(stuff)**
