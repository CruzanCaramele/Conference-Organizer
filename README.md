Visit the application at this [link][7]

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


