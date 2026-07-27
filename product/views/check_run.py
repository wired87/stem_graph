import os
import shutil
import subprocess
import tempfile
from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


# Dummy-Funktion für deine ID-Generierung
def generate_id():
    import uuid
    return f"run_{uuid.uuid4().hex[:8]}"


class DockerStatusAndDownloadView(APIView):
    def get(self, request, container_id, *args, **kwargs):
        """
        Fragt den Status eines Docker-Containers ab.
        Falls fertig: Zippt die Daten aus dem lokalen Temp-Ordner und lädt sie herunter.
        """
        # --- 1. DOCKER STATUS ABFRAGEN ---
        try:
            # Holt den aktuellen Status (z.B. running, exited)
            status_cmd = ["docker", "inspect", "-f", "{{.State.Status}}", container_id]
            container_status = subprocess.run(status_cmd, capture_output=True, text=True, check=True).stdout.strip()
        except subprocess.CalledProcessError:
            return Response(
                {"error": f"Container mit ID '{container_id}' wurde nicht gefunden."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Wenn der Container noch arbeitet
        if container_status == "running":
            return Response(
                {"status": "running", "message": "Der Prozess läuft noch. Bitte später erneut abfragen."},
                status=status.HTTP_202_ACCEPTED
            )

        # Wenn der Container gestoppt ist, prüfen wir den Exit-Code
        if container_status == "exited":
            exit_code_cmd = ["docker", "inspect", "-f", "{{.State.ExitCode}}", container_id]
            exit_code = subprocess.run(exit_code_cmd, capture_output=True, text=True).stdout.strip()

            if exit_code != "0":
                return Response(
                    {"status": "failed", "error": f"Der Container ist mit Fehlercode {exit_code} abgestürzt."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            # Für Zustände wie 'paused', 'restarting' etc.
            return Response(
                {"status": container_status, "message": f"Container befindet sich im Zustand: {container_status}"},
                status=status.HTTP_200_OK
            )

        # --- 2. DATEN VERARBEITEN (Wenn Container erfolgreich beendet) ---

        # WICHTIG: Hier musst du den Pfad zu DEINEM lokalen Temp-Ordner auf dem Host wissen.
        # Da dieser Request ein neuer HTTP-Aufruf ist, musst du den Pfad entweder aus einer DB holen,
        # oder er lässt sich über die container_id rekonstruieren (z.B. wenn der Temp-Ordner so hieß).
        # Hier als Platzhalter:
        host_output_dir = f"C:\\Users\\Bernhard\\AppData\\Local\\Temp\\{container_id}"

        if not os.path.exists(host_output_dir) or not os.listdir(host_output_dir):
            return Response(
                {"status": "no_data", "message": "Der Container war erfolgreich, aber es wurden keine Daten gefunden."},
                status=status.HTTP_204_NO_CONTENT
            )

        # Temporäres Verzeichnis für das ZIP-Archiv selbst erstellen
        # (Damit das ZIP nicht IM Datenordner liegt und sich selbst mitzippt)
        zip_temp_dir = tempfile.mkdtemp()
        run_id = generate_id()
        archive_base_path = os.path.join(zip_temp_dir, run_id)

        try:
            # Erstellt ein ZIP-Archiv aus dem Inhalt von host_output_dir
            zip_path = shutil.make_archive(archive_base_path, 'zip', host_output_dir)

            # Datei im Binärmodus öffnen
            bz_content = open(zip_path, "rb")

            # --- 3. AUFRÄUMEN ---
            # Container entfernen, da er fertig ist und nicht mehr gebraucht wird
            subprocess.run(["docker", "rm", container_id], capture_output=True)

            # Lokales Datenverzeichnis auf dem Host löschen (Dein altes tmp_store.cleanup())
            shutil.rmtree(host_output_dir, ignore_errors=True)

            # --- 4. SEAMLESS DOWNLOAD RESPONSE ---
            response = FileResponse(
                bz_content,
                as_attachment=True,
                filename=f"{run_id}.zip",
                content_type="application/zip"
            )

            # Wichtig: Das temporäre ZIP-Archiv löschen, sobald die Response gesendet wurde
            # Django schließt die Datei nach dem Senden, danach greift dieser Callback
            response.closed_callback = lambda: shutil.rmtree(zip_temp_dir, ignore_errors=True)
            return response

        except Exception as e:
            # Falls beim Zippen was schiefgeht, aufräumen
            shutil.rmtree(zip_temp_dir, ignore_errors=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)