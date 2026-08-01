from django.http import HttpResponse
from django.shortcuts import render


def favicon(request):
    """Avoid a noisy development-server 404 when no brand icon is installed."""
    return HttpResponse(status=204)


def home(request):
    return render(request, "index.html", {"theme": "workflow"})


def cnv_workspace(request):
    return render(request, "workspaces/cnv.html", {"theme": "cnv"})


def go_workspace(request):
    return render(request, "workspaces/go.html", {"theme": "go"})


def file_workspace(request):
    return render(request, "workspaces/files.html", {"theme": "files"})


def compute_workspace(request):
    return render(request, "workspaces/compute.html", {"theme": "compute"})
