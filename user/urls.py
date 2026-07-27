# User section URL routes
from django.urls import path

from user.views.delete_file import DeleteFileView
from user.views.get_file import GetFileView
from user.views.get_file_names import GetFileNamesView
from user.views.set_file import SetFileView
from user.views.update_file import UpdateFileView

# User API endpoint patterns
urlpatterns = [
    # Get-file_master-names route
    path('get-file_master-names/', GetFileNamesView.as_view(), name='user-get-file_master-names'),
    # Get-file_master route
    path('get-file_master/', GetFileView.as_view(), name='user-get-file_master'),
    # Set-file_master route
    path('set-file_master/', SetFileView.as_view(), name='user-set-file_master'),
    # Delete-file_master route
    path('delete-file_master/', DeleteFileView.as_view(), name='user-delete-file_master'),
    # Update-file_master route
    path('update-file_master/', UpdateFileView.as_view(), name='user-update-file_master'),
]
