from django.conf.urls import patterns, url

import views

urlpatterns = patterns('',
    url(r'^$', views.index),
    url(r'^searchtask', views.search_task),
    url(r'^createtask', views.create_task),
    url(r'^opentask', views.open_task),
    url(r'^taskjobs', views.task_jobs),
    url(r'^taskreports', views.task_reports),
    url(r'^checkscanner', views.check_scanner),
)
