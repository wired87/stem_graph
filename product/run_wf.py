from utils._docker.check_image import check_docker_img_exists

dir = r"/product/executable/example_data"
from utils.run_subprocess import exec_cmd

import dotenv
dotenv.load_dotenv()

import os



def run_docker_stemcnv(dir, custom_env_value: "STATIC" or "RUN"):
    img_exists:bool or None = check_docker_img_exists(
        os.getenv("DOCKER_IMAGE")
    )
    if img_exists is None:
        cli_arguments = [
            "docker", "build", "-t",
            os.getenv("DOCKER_IMAGE"),
            os.path.abspath(os.path.join("executable"))
        ]

        result = exec_cmd(cli_arguments, timeout=900)
        print("docker build result", result)
        if "err" in result.lower():
            raise ValueError("invalid args")
        else:
            return run_docker_stemcnv(dir, custom_env_value)
    else:
        try:
            cli_arguments = [
                "docker", "run", "--rm",
                "-e", f"STEM_PROCESS={custom_env_value}",  # <-- Custom ENV Var für den Container
                "-e", "STEMCNV_CACHE=/tmp/stemcnv_cache",  # <-- Avoid POSIX errors on Windows bind mounts
                "--mount", f"type=bind,source={dir},target=/app/data",
                os.getenv("DOCKER_IMAGE"),
            ]

            result = exec_cmd(cli_arguments, timeout=900)
            print("result", result)
            try:
                return result.stdout.strip()
            except Exception as e:
                print("reuslt", e)
                return result
        except Exception as e:
            print("Err exec docker and get results",e)


