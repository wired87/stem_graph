# File section URL routes
from django.urls import path

from file_master.views.delete_file import DeleteFileView
from file_master.views.get_file import GetFileView
from file_master.views.get_file_names import GetFileNamesView
from file_master.views.set_file import SetFileView
from file_master.views.update_file import UpdateFileView

# File API endpoint patterns
urlpatterns = [
    # Get-file_master-names route
    path('get-file_master-names/', GetFileNamesView.as_view(), name='file_master-get-file_master-names'),
    # Get-file_master route
    path('get-file_master/', GetFileView.as_view(), name='file_master-get-file_master'),
    # Set-file_master route
    path('set-file_master/', SetFileView.as_view(), name='file_master-set-file_master'),
    # Delete-file_master route
    path('delete-file_master/', DeleteFileView.as_view(), name='file_master-delete-file_master'),
    # Update-file_master route
    path('update-file_master/', UpdateFileView.as_view(), name='file_master-update-file_master'),
]
