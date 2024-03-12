import logging
import subprocess


try:
    logging.basicConfig(
        filename="/home/appscontroller/appstrafficcontroller/app/logs/server_commands.log",
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
except FileNotFoundError:
    try:
        logging.basicConfig(
            filename="app/logs/server_commands.log",
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    except FileNotFoundError:
        logging.basicConfig(
            filename="logs/server_commands.log",
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )


def run_sudo_command(command: list) -> subprocess.CompletedProcess:
    """
    Adds echo & password to command, then runs it with sudo

    Args:
        command (list): list of command arguments

    Returns:
        subprocess.CompletedProcess: result of command execution
    """
    password = "appstraffic2023"
    full_command = f'echo {password} | sudo -S {" ".join(command)}'
    result = subprocess.run(
        full_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    return result


def add_domain_to_nginx(domain: str, subdomains: list) -> bool:
    """
    Add domain with subdomains to nginx configuration file and restart nginx

    Args:
        domain (str): domain to add
        subdomains (list): list of subdomains

    Returns:
        bool: True if success, False if error
    """
    server_row = " ".join([f"server_name {domain}"] + subdomains)
    # Create a configuration file for domain
    config = f"""
\n
server {{
    {server_row};

    location / {{
        include proxy_params;
        proxy_pass http://unix:/home/appscontroller/app/appscontroller.sock;
    }}
}}
"""

    logging.info(f"Wriring config file for {domain}")
    # Record the configuration file in the file system
    filename = "/etc/nginx/sites-available/appscontroller"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(config)
    logging.info(f"Config file for {domain} was written")

    # try:
    #     # Create a symbolic link to the configuration file in sites-enabled
    #     run_sudo_command([
    #         'ln',
    #         # '-s',
    #         f'/etc/nginx/sites-available/{domain}',
    #         f'/etc/nginx/sites-enabled/{domain}'
    #         ])

    #     # Check the nginx configuration and restart the server
    #     run_sudo_command(['nginx', '-t'])
    run_sudo_command(["systemctl", "reload", "nginx"])
    run_sudo_command(["systemctl", "restart", "nginx"])
    logging.info("Nginx was restarted")
    # except Exception as e:
    #     print(e)
    #     # If an error occurs, delete the configuration file
    #     run_sudo_command(['rm', f'/etc/nginx/sites-available/{domain}'])
    #     run_sudo_command(['rm', f'/etc/nginx/sites-enabled/{domain}'])

    #     return False

    return True


def install_certbot_certificate(domain):
    # Generate a SSL certificate
    install_result = run_sudo_command(
        [
            "certbot",
            "certonly",
            "--nginx",
            "-d",
            domain,
            "-d",
            "www." + domain,
            "--non-interactive",
            "--agree-tos",
            "-m",
            "confirm@coffeemail.space",
        ]
    )
    print(install_result)

    return True
