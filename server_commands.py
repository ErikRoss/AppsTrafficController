import subprocess


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
        full_command, 
        shell=True, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE
        )
    
    return result

def add_domain_to_nginx(domain) -> bool:
    """
    Add domain to nginx configuration file and restart nginx
    
    Args:
        domain (str): domain to add
        
    Returns:
        bool: True if success, False if error
    """
    # Create a configuration file for domain
    config = f'''
    server {{
        listen 80;
        server_name {domain};
        return 301 https://$host$request_uri;
    }}

    server {{
        listen 443 ssl;
        server_name {domain};
        ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
        include /etc/letsencrypt/options-ssl-nginx.conf;
        ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

        location / {{
            proxy_pass http://localhost:5000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
    '''

    # Record the configuration file in the file system
    with open(f'/etc/nginx/sites-available/{domain}', 'w') as f:
        f.write(config)

    try:
        # Create a symbolic link to the configuration file in sites-enabled
        run_sudo_command([
            'ln', 
            # '-s', 
            f'/etc/nginx/sites-available/{domain}', 
            f'/etc/nginx/sites-enabled/{domain}'
            ])

        # Check the nginx configuration and restart the server
        run_sudo_command(['nginx', '-t'])
        run_sudo_command(['systemctl', 'reload', 'nginx'])
    except Exception as e:
        print(e)
        # If an error occurs, delete the configuration file
        run_sudo_command(['rm', f'/etc/nginx/sites-available/{domain}'])
        run_sudo_command(['rm', f'/etc/nginx/sites-enabled/{domain}'])
        
        return False
    
    return True

def install_certbot(domain):
    # Install Certbot and generate a SSL certificate
    run_sudo_command(['apt-get', 'update'])
    run_sudo_command(['apt-get', 'install', '-y', 'certbot'])
    run_sudo_command([
        'certbot', 
        'certonly', 
        '--nginx', 
        '-d', 
        domain, 
        '--non-interactive', 
        '--agree-tos', 
        '-m', 
        'youremail@example.com'
        ])
