from django.urls import path

from firegraph.graph.dj.visual import GraphLookup
from firegraph.graph.dj.brain_test import BrainTestView
from firegraph.graph.dj.thalamus_test import ThalamusTestView

app_name = "graph"
urlpatterns = [
    # client
    path('view/', GraphLookup.as_view()),
    path('brain/test/', BrainTestView.as_view()),
    path('thalamus/test/', ThalamusTestView.as_view()),
]

