from flask import Flask, make_response, render_template, request, redirect, url_for, session, flash, send_file, stream_template
from flask_session import Session
from flask.views import View
import requests
from pydantic import BaseModel
import datetime
from flask_caching import Cache
import configparser

config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300
}

app = Flask(__name__)
SESSION_TYPE = 'filesystem'
app.config.from_object(__name__)

app.config.from_mapping(config)
cache = Cache(app)
cache.init_app(app)
Session(app)

#import config.ini api_url variable from FASTAPI
config = configparser.ConfigParser()
config.read('config.ini')
api_url = config['FASTAPI']['api_url']


def set_cookie(response):
    session['token'] = response.json()['token']
    session['type'] = response.json()['type']
    session['username'] = response.json()['username']

def validate_token():
    token = get_token()
    response = requests.get(api_url + '/token', headers = {'Authorization': 'Bearer ' + token})
    if response.status_code == 200:
        return True
    else:
        return False

def get_token():
    token = session.get('token', 'No token')
    return token

def get_username():
    username = session.get('username', 'anonymous')
    return username

def get_intervals():
    if validate_token() == True:
        token = get_token()
        response = requests.get(api_url + '/config/interval/all', headers = {'Authorization': 'Bearer ' + token}, params={'token': token})
        if response.status_code == 200:
            intervals = response.json()["intervals"]
            return intervals
        else:
            return []
            
def get_types():
    if validate_token() == True:
        token = get_token()
        response = requests.get(api_url + '/config/type/all', headers = {'Authorization': 'Bearer ' + token}, params={'token': token})
        if response.status_code == 200:
            types = response.json()["types"]
            return types
        else:
            return []

@cache.cached(timeout=120, key_prefix='all_directories')
def get_all_directories():
    if validate_token() == True:
        token = get_token()
        response = requests.get(api_url + '/directory/all', headers = {'Authorization': 'Bearer ' + token})
        directories_full = response.json().get('directories', 'No directories')
        #get all directory_name from directories
        directories = [directory['directory_name'] for directory in directories_full]
        if response.status_code == 200:
            return directories, directories_full

@cache.cached(timeout=120, key_prefix='disk_space')
def get_disk_space():
    if validate_token() == True:
        token = get_token()
        response = requests.get(api_url + '/disk/space', headers = {'Authorization': 'Bearer ' + token})
        chart_data = response.json()
        return chart_data


def get_folder_size(directory):
    if validate_token() == True:
        token = get_token()
        response = requests.get(api_url + '/directory/size/', headers = {'Authorization': 'Bearer ' + token}, params={'folder_name': directory})
        folder_size = response.json()
        return folder_size

@cache.cached(timeout=120, key_prefix='get_all_folders_size_cache')
def get_all_folders_size():
    if validate_token() == True:
        token = get_token()
        response = requests.get(api_url + '/directory/size/all', headers = {'Authorization': 'Bearer ' + token})
        all_folders_size = response.json()
        return all_folders_size


def is_admin_from_cache():
    isAdmin = session.get('type', 'No type')
    if isAdmin == 'admin':
        return True
    else:
        return False

@app.template_filter('format_date')
def format_date(value, format):
    date = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    if format == 'short':
        format = "%d/%m/%Y"
        return date.strftime(format)
    elif format == 'long':
        format = "%d/%m/%Y %H:%M:%S"
        return date.strftime(format)
    elif format == 'time':
        format = "%H:%M:%S"
        return date.strftime(format)

def get_all_configs():
    if validate_token() == True:
        token = get_token()
        response = requests.get(api_url + '/config/all', headers = {'Authorization': 'Bearer ' + token}, params={'token': token})
        all_configs = response.json()["all_configs"]
        return all_configs

def get_all_backups():
    if validate_token() == True:
        token = get_token()
        response = requests.get(api_url + '/backup/all', headers = {'Authorization': 'Bearer ' + token}, params={'token': token})
        backups = response.json()["backups"]
        return backups

class FlaskCache:
    def __init__(self, cache):
        self.cache = cache
    
    def delete_cache(cache_name):
        cache.delete(cache_name)

@app.route("/")
def index():
    if validate_token() == True:
        return redirect(url_for('startpage'))
    else:
        return render_template('index.html', title='Home')

@app.route('/gettoken/')
def get():
    return session.get('token', 'No token')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user_object = {
            'username': username,
            'password': password
        }
        response = requests.post(api_url + '/login', json=user_object)
        if response.status_code == 200:
            set_cookie(response)
            return redirect(url_for('startpage'))
        else:
            flash(response.json()['detail'], 'error')
            return redirect(url_for('login'))
    else:
        return render_template('login.html', title='Login')

@app.route("/logout", methods=['POST'])
def logout():
    token = session.get('token', 'No token')
    token_object = {
        'token': token
    }
    response = requests.post(api_url + '/logout', headers = {'Authorization': 'Bearer ' + token}, json=token_object)
    if response.status_code == 200:
        session.clear()
        return redirect(url_for('index'))
    else:
        raise Exception(response.json()['detail'])
    

@app.route("/adduser", methods=['GET', 'POST'])
def adduser():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        user_object = {
            'username': username,
            'password': password,
            'email': email
        }
        response = requests.post(api_url + '/user', json=user_object)
        if response.status_code == 200:
            flash('Usuário adicionado com sucesso!')
            return redirect(url_for('login'))
        else:
            flash('Erro ao adicionar usuário!')
            return redirect(url_for('adduser'))

    return render_template('adduser.html')

@app.route("/startpage", methods=['GET', 'POST'])
def startpage():
    if validate_token() == True:
        flashes = session.get('_flashes', [])
        print(flashes)
        return render_template('start_page.html', title="Inicio")
    else:
        return redirect(url_for('index'))

@app.route("/adddirectory", methods=['POST'])
def adddirectory():
    if validate_token() == True:
        directory_name = request.form['folderName']
        directory_path = request.form['folderPath']
        username = get_username()
        token = get_token()
        directory_object = {
            'directory_name': directory_name,
            'directory_path': directory_path,
            'username': username
        }
        response = requests.post(api_url + '/directory', headers={'Authorization': 'Bearer ' + token}, json=directory_object)
        if response.status_code == 200:
            FlaskCache.delete_cache('all_directories')
            flash('Directory added', 'success')
            return redirect(url_for('startpage'))
        else:
            flash(response.json()['detail'], 'error')
            return redirect(url_for('startpage'))

@app.route("/deletedirectory", methods=['POST'])
def deletedirectory():
    if validate_token() == True:
        directory_name = request.form['selected_directory']
        username = get_username()
        token = get_token()
        directory_object = {
            'directory_name': directory_name
        }
        response = requests.delete(api_url + '/directory', headers={'Authorization': 'Bearer ' + token}, json=directory_object)
        if response.status_code == 200:
            FlaskCache.delete_cache('all_directories')
            return redirect(url_for('startpage'))
        else:
            flash(response.json()['detail'], 'error')
            return redirect(url_for('startpage'))

@app.route("/listdirectoryfiles", methods=['GET', 'POST'])
def listdirectoryfiles():
    if validate_token() == True:
        if request.method == 'GET':
            directory_name = request.args.get('directory_name')
            token = get_token()
            directory_object = {
                'directory_name': directory_name
            }
            folder_size = get_folder_size(directory_name)
            response = requests.get(api_url + '/directory/file/all', headers={'Authorization': 'Bearer ' + token}, json=directory_object)
            if response.status_code == 200:
                files = response.json().get('files', 'No files')
                return render_template('files.html', files=files, folder_size=folder_size, title=directory_name)
            else:
                flash("Pasta não encontrada", 'error')
                return redirect(url_for('startpage'))

@app.route("/downloadfile", methods=['GET', 'POST'])
def downloadfile():
    if validate_token() == True:
        if request.method == 'GET':
            file_path = request.args.get('file_path_download')
            file_name = request.args.get('file_name_download')
            token = get_token()
            response = requests.get(api_url + '/downloadfile', headers={'Authorization': 'Bearer ' + token}, params={'file_path': file_path})
            if response.status_code == 200:
                return send_file(file_path, as_attachment=True, download_name=file_name)
            else:
                flash(response.json(), 'error')
                #keep user in the same page
                return redirect(request.referrer)

@app.route("/change_user_password", methods=['GET', 'POST'])
def change_user_password():
    if validate_token() == True:
        if request.method == 'POST':
            username = get_username()
            token = get_token()
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            user_object = {
                'username': username,
                'old_password': old_password,
                'new_password': new_password,
                'token': token
            }
            response = requests.put(api_url + '/user/password', headers={'Authorization': 'Bearer ' + token}, json=user_object)
            if response.status_code == 200:
                flash(response.json()['detail'], 'success')
                return redirect(url_for('startpage'))
            else:
                flash(response.json()['detail'], 'error')
                return redirect(url_for('startpage'))

@app.route("/config", methods=['GET', 'POST'])
def config():
    if validate_token() == True and is_admin_from_cache() == True:
        if request.method == 'GET':
            users = list_users()
            configs = get_all_configs()
            return render_template('config.html', users=users, configs=configs, title="Configurações")
    else:
        return redirect(url_for('startpage'))

@app.route("/backup", methods=['GET', 'POST'])
def backup():
    if validate_token() == True and is_admin_from_cache() == True:
        if request.method == 'GET':
            backups = get_all_backups()
            return render_template('backup.html', title="Backup", backups=backups)
    else:
        return redirect(url_for('startpage'))

@app.route("/config/<username>/<int:authorized>", methods=['POST'])
def config_user_authorized(username, authorized):
    if validate_token() == True:
        if request.method == 'POST':
            token = get_token()
            if authorized == 1:
                authorized_status = True
            else:
                authorized_status = False
            user_object = {
                'username': username,
                'autorized': authorized_status
            }
            response = requests.put(api_url + '/user/authorized', headers = {'Authorization': 'Bearer ' + token}, params={'token':token} ,json=user_object)
            if response.status_code == 200:
                flash(response.json()['detail'], 'success')
                return redirect(url_for('config'))
            else:
                flash(response.json()['detail'], 'error')
                return redirect(url_for('config'))

@app.route("/config/user", methods=['POST'])
def config_user_update_fields():
    if validate_token() == True and is_admin_from_cache() == True:
        if request.method == 'POST':
            token = get_token()
            old_username = request.form['oldUserName']
            username = request.form['userName']
            email = request.form['userEmail']
            userType = request.form['userType']

            #check if username, email or userType is empty
            if username == '' or email == '' or userType == '':
                flash("Preencha todos os campos", 'error')
                return redirect(url_for('config'))
            else:
                response_name = requests.put(api_url + '/user/name', headers={'Authorization': 'Bearer ' + token}, params={'token':token} ,json={'old_username': old_username, 'new_username': username})
                response_email = requests.put(api_url + '/user/email', headers={'Authorization': 'Bearer ' + token}, params={'token':token} ,json={'username':username, 'email': email})
                response_type = requests.put(api_url + '/user/type', headers={'Authorization': 'Bearer ' + token}, params={'token':token} ,json={'username':username, 'type': userType})

                if response_name.status_code == 200 or response_email.status_code == 200 or response_type.status_code == 200:
                    flash("Informações atualizadas com sucesso", 'success')
                    return redirect(url_for('config'))
                else:
                    flash("Erro ao atualizar informações", 'error')
                    return redirect(url_for('config'))

@app.route("/list_users", methods=['GET', 'POST'])
def list_users():
    if validate_token() == True:
        if request.method == 'GET':
            token = get_token()
            response = requests.get(api_url + '/user/all', headers={'Authorization': 'Bearer ' + token}, params={'token':token})
            if response.status_code == 200:
                users = response.json().get('users', 'No users')
                return users
            else:
                return ''

@app.route("/delete_user/<username>", methods=['POST'])
def delete_user(username):
    if validate_token() == True:
        if request.method == 'POST':
            token = get_token()
            response = requests.delete(api_url + '/user/', headers={'Authorization': 'Bearer ' + token}, params={'token':token}, json={'username': username})
            if response.status_code == 200:
                flash('User deleted', 'success')
                return redirect(url_for('config'))
            else:
                flash(response.json()['detail'], 'error')
                return redirect(url_for('config'))


@app.route("/config/config", methods=['POST'])
def config_config_update_fields():
    if validate_token() == True and is_admin_from_cache() == True:
        if request.method == 'POST':
            token = get_token()
            config_name = request.form['configName']
            config_value = request.form['configValue']
            #check if config_name or config_value is empty
            if config_name == '' or config_value == '':
                flash("Preencha todos os campos", 'error')
                return redirect(url_for('config'))
            else:
                response = requests.put(api_url + '/config', headers={'Authorization': 'Bearer ' + token}, params={'token':token} ,json={'config_name': config_name, 'config_value': config_value})
                if response.status_code == 200:
                    backups = response.json()
                    return backups
                else:
                    return ''

@app.route("/add_backup", methods=['GET', 'POST'])
def add_backup():
    if validate_token() == True and is_admin_from_cache() == True:
        if request.method == 'POST':
            token = get_token()
            username = get_username()
            backup = {
            'backup_name': request.form['backupName'],
            'backup_path': request.form['backupPath'],
            'time': request.form['backupTime'],
            'interval': request.form['backupInterval'],
            'day': '',
            'connection_string': request.form['backupString'],
            'backup_type': request.form['backupType'],
            'backup_user': request.form['backupUser'],
            'backup_password': request.form['backupPassword'],
            'username': username
            }
            response = requests.post(api_url + '/backup', headers={'Authorization': 'Bearer ' + token}, params={'token':token} ,json=backup)
            if response.status_code == 200:
                flash('Backup added', 'success')
                return redirect(url_for('backup'))
            else:
                flash(response.json()['detail'], 'error')
                return redirect(url_for('backup'))
#Jinja2 global functions
app.jinja_env.globals.update(get_disk_space=get_disk_space, isAdmin=is_admin_from_cache, get_all_directories=get_all_directories, get_all_folders_size=get_all_folders_size, get_intervals=get_intervals, get_types=get_types)