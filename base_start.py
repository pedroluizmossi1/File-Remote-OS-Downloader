import sqlalchemy
from datetime import timedelta
from datetime import datetime as dt
import datetime
from sqlalchemy.orm import declarative_base, sessionmaker
import time
from fastapi import HTTPException, Header, status, Depends
import configparser
from pydantic import BaseModel
import bcrypt
from uuid import uuid4
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, Request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
from pytz import utc

timezone = datetime.timezone(datetime.timedelta(hours=-3))
timezone_br = datetime.datetime.now(timezone)

database_name = 'sqlite:///base.db'

engine = sqlalchemy.create_engine(
    database_name, connect_args={'check_same_thread': False})
metadata = sqlalchemy.MetaData()
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()


scheduler = BackgroundScheduler()

jobstores = {
    'default': SQLAlchemyJobStore(url=database_name)
}
executors = {
    'default': ThreadPoolExecutor(20),
    'processpool': ProcessPoolExecutor(5)
}
job_defaults = {
    'coalesce': False,
    'max_instances': 3
}
scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults, timezone=utc)

scheduler.start()

def hash_password(password):
    password = str(password).encode('utf-8')
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())
    return hashed

def check_password(password, hashed):
    password = str(password).encode('utf-8')
    if bcrypt.checkpw(password, hashed):
        return True
    else:
        return False

#def to generate token from username and password
def generate_token():
    token = str(uuid4())
    return token

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            if not self.verify_jwt(credentials.credentials):
                raise HTTPException(status_code=403, detail="Invalid token or expired token.")
            return credentials.credentials
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")

    def verify_token_from_db(self, token):
        token = session.query(Token).filter_by(token=token).first()
        if token != None:
            return True
        else:
            return False
    #verify token
    def verify_jwt(self, token):
        if self.verify_token_from_db(token):
            return True
        else:
            return False


class Users(Base):
    __tablename__ = 'users'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    username = sqlalchemy.Column(sqlalchemy.String, unique=True)
    password = sqlalchemy.Column(sqlalchemy.String)
    type = sqlalchemy.Column(sqlalchemy.String, default='user')
    email = sqlalchemy.Column(sqlalchemy.String)
    date = sqlalchemy.Column(
    sqlalchemy.DateTime, default=datetime.datetime.utcnow),
    autorized = sqlalchemy.Column(sqlalchemy.Boolean, default=False)

    def __repr__(self):
        return f"User(id={self.id}, username={self.username}, password={self.password}, type={self.type}, email={self.email})"

    class Api_add(BaseModel):
        username: str
        password: str
        email: str

        def add_user(username, password, email):
            user = Users(username=username, password=hash_password(password), type='user', email=email)
            session.add(user)
            session.commit()
            return user

    class Api_delete(BaseModel):
        username: str

        def delete_user(username):
            user = session.query(Users).filter_by(username=username).first()
            if user is None:
                return None
            else:
                session.delete(user)
                session.commit()
                return user

    class Api_login(BaseModel):
        username: str
        password: str

        def login_user(username, password):
            user = session.query(Users).filter_by(username=username).first()
            if user is None:
                return None
            else:
                if check_password(password, user.password):
                    token = generate_token()
                    Token.add_token(token, username)
                    user_type = user.type
                    return {'token':token, 'type':user_type}
                else:
                    return None

    class Api_update_password(BaseModel):
        username: str
        old_password: str
        new_password: str
        token: str

        def update_password(username, old_password, new_password, token):
            user = session.query(Users).filter_by(username=username).first()
            checked_password = check_password(old_password, user.password)
            checked_username = check_username_with_token(token)
            if checked_password and checked_username:
                user.password = hash_password(new_password)
                session.commit()
                return user
            else:
                return None

    class Api_update_username(BaseModel):
        old_username: str
        new_username: str

        def update_username(old_username, new_username):
            try:
                user = session.query(Users).filter_by(username=old_username).first()
                user.username = new_username
                session.commit()
                return user
            except Exception as error:
                return None

    class Api_update_email(BaseModel):
        username: str
        email: str

        def update_email(username, email):
            try:
                user = session.query(Users).filter_by(username=username).first()
                user.email = email
                session.commit()
                return user
            except Exception as error:
                return None
    
    class Api_update_type(BaseModel):
        username: str
        type: str

        def update_type(username, type):
            user = session.query(Users).filter_by(username=username).first()
            try:
                if type == '1':
                    user.type = 'admin'
                    session.commit()
                    return user
                elif type == '2':
                    user.type = 'user'
                    session.commit()
                    return user
                else:
                    return None
            except Exception as error:
                return None

    class Api_check_admin(BaseModel):
        username: str

        def check_admin(username):
            user = session.query(Users).filter_by(username=username).first()
            if user.type == 'admin':
                return True
            else:
                return False

    class Api_update_autorized(BaseModel):
        username: str
        autorized: bool

        def update_autorized(username, autorized):
            user = session.query(Users).filter_by(username=username).first()
            try:
                user.autorized = autorized
                session.commit()
                return user
            except Exception as error:
                return None


class Token(Base):
    __tablename__ = 'token'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    token = sqlalchemy.Column(sqlalchemy.String, unique=True)
    username = sqlalchemy.Column(sqlalchemy.String)
    date = sqlalchemy.Column(sqlalchemy.DateTime, default=timezone_br)

    def __repr__(self):
        return f"Token(id={self.id}, token={self.token}, username={self.username})"

    def add_token(token, username):
        token = Token(token=token, username=username)
        session.add(token)
        session.commit()
        return token

# create directorys table

class Directories(Base):
    __tablename__ = 'Directories'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    directory_name = sqlalchemy.Column(sqlalchemy.String, unique=True)
    directory_path = sqlalchemy.Column(sqlalchemy.String, unique=True)
    username = sqlalchemy.Column(sqlalchemy.String)
    date = sqlalchemy.Column(
        sqlalchemy.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"Directories(id={self.id}, directory_name={self.directory_name}, directory_path={self.directory_path}, username={self.username})"

    class Api_add(BaseModel):
        directory_name: str
        directory_path: str
        username: str

        def add_directory(directory_name, directory_path, username):
            try:
                directory = Directories(directory_name=directory_name, directory_path=directory_path, username=username)
                session.add(directory)
                session.commit()
                return directory
            except Exception as error:
                session.flush()
                session.rollback()
                return None

    class Api_delete(BaseModel):
        directory_name: str

        def delete_directory(directory_name):
            directory = session.query(Directories).filter_by(directory_name=directory_name).first()
            if directory is None:
                return None
            else:
                session.delete(directory)
                session.commit()
                return directory

    class Api_list(BaseModel):
        directory_name: str

        def list_directory(directory_name):
            directory = session.query(Directories).filter_by(directory_name=directory_name).first()
            if directory is None:
                return None
            else:
                return directory
        
        def list_all_directories():
            directory = session.query(Directories).all()
            if directory is None:
                return None
            else:
                return directory



class Config(Base):
    __tablename__ = 'config'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    config_name = sqlalchemy.Column(sqlalchemy.String, unique=True)
    config_value = sqlalchemy.Column(sqlalchemy.String, unique=True)
    config_description = sqlalchemy.Column(sqlalchemy.String)
    username = sqlalchemy.Column(sqlalchemy.String)
    date = sqlalchemy.Column(
        sqlalchemy.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"Config(id={self.id}, config_name={self.config_name}, config_value={self.config_value}, username={self.username})"

    def check_config(config_name):
        config = session.query(Config).filter_by(config_name=config_name).first()
        if config is None:
            return None
        else:
            return config.config_value

    def create_config(config_name, config_value, config_description, username):
        config = Config(config_name=config_name, config_value=config_value, config_description=config_description, username=username)
        session.add(config)
        session.commit()
        return config

    class Api_update(BaseModel):
        config_name: str
        config_value: str
    
        def update_config(config_name, config_value, username):
            config = session.query(Config).filter_by(config_name=config_name).first()
            config.config_value = config_value
            config.username = username
            config.date = timezone_br
            session.commit()
            if config_name == 'api_url':
                config = configparser.ConfigParser()
                with open('config.ini', 'w') as configfile:
                    config['FASTAPI'] = {'api_url': config_value}
                    config.write(configfile)
                

            return config
    
    def get_all_configs():
        config = session.query(Config).all()
        return config


class Backups(Base):
    __tablename__ = 'backups'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    backup_name = sqlalchemy.Column(sqlalchemy.String, unique=True)
    backup_path = sqlalchemy.Column(sqlalchemy.String)
    time = sqlalchemy.Column(sqlalchemy.String)
    interval = sqlalchemy.Column(sqlalchemy.String)
    day = sqlalchemy.Column(sqlalchemy.String)
    connection_string = sqlalchemy.Column(sqlalchemy.String)
    backup_type = sqlalchemy.Column(sqlalchemy.String)
    backup_status = sqlalchemy.Column(sqlalchemy.String)
    backup_user = sqlalchemy.Column(sqlalchemy.String)
    backup_password = sqlalchemy.Column(sqlalchemy.String)
    username = sqlalchemy.Column(sqlalchemy.String)
    date = sqlalchemy.Column(
        sqlalchemy.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"Backups(id={self.id}, backup_name={self.backup_name}, backup_path={self.backup_path}, time={self.time}, interval={self.interval}, day={self.day} connection_string={self.connection_string}, backup_type={self.backup_type}, backup_status={self.backup_status}, backup_user={self.backup_user}, backup_password={self.backup_password}, username={self.username})"

    class Api_add(BaseModel):
        backup_name: str
        backup_path: str
        time: str
        interval: str
        day: str
        connection_string: str
        backup_type: str
        backup_user: str
        backup_password: str
        username: str

        def add_backup(backup_name, backup_path, time, interval, day, connection_string, backup_type, backup_user, backup_password, username):
            try:
                password = hash_password(backup_password)
                backup = Backups(backup_name=backup_name, backup_path=backup_path, time=time, interval=interval, day=day, connection_string=connection_string, backup_type=backup_type, backup_status=True, backup_user=backup_user, backup_password=password, username=username)
                session.add(backup)
                session.commit()
                try:
                    today = datetime.datetime.now()
                    if datetime.datetime.strptime(time, '%H:%M') > today:
                        backup_next = today.replace(hour=int(time[0:2]), minute=int(time[3:5]))
                    else:
                        backup_next = today.replace(hour=int(time[0:2]), minute=int(time[3:5])) + timedelta(days=1)
                    backup_last = today - timedelta(days=1)
                    backup_job = Backups_jobs.Api_create.add_backup_job(5,'',backup_next, backup_last ,1, '', '')
                    backup_job_id = str(backup_job.id)
                    scheduler.add_job(print_hello,
                        'interval',
                        seconds= interval,
                        id=backup_job_id,
                        name=backup_name,
                        next_run_time=backup_next,
                        replace_existing=True
                    )
                except Exception as error:
                    print(error)
                    session.flush()
                    session.rollback()
                    return error
                return backup
            except Exception as error:
                session.flush()
                session.rollback()
                return error



    class Api_update(BaseModel):
        backup_name: str
        backup_path: str
        time: str
        interval: str
        day: str
        connection_string: str
        backup_type: str
        backup_status: str
        backup_user: str
        backup_password: str
        username: str

        def update_backup(backup_name, backup_path, time, interval, day, connection_string, backup_type, backup_status, backup_user, backup_password, username):
            backup = session.query(Backups).filter_by(backup_name=backup_name).first()
            backup.backup_path = backup_path
            backup.time = time
            backup.interval = interval
            backup.day = day
            backup.connection_string = connection_string
            backup.backup_type = backup_type
            backup.backup_status = backup_status
            backup.backup_user = backup_user
            backup.backup_password = backup_password
            backup.username = username
            backup.date = timezone_br
            session.commit()
            return backup

    class Api_list(BaseModel):
        backup_name: str

        def list_backup(backup_name):
            backup = session.query(Backups).filter_by(backup_name=backup_name).first()
            return backup
        
        def list_all_backups():
            backup = session.query(Backups).all()
            return backup

    class Api_delete(BaseModel):
        backup_name: str

        def delete_backup(backup_name):
            backup = session.query(Backups).filter_by(backup_name=backup_name).first()
            session.delete(backup)
            session.commit()
            return backup

class Intervals(Base):
    __tablename__ = 'intervals'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    interval = sqlalchemy.Column(sqlalchemy.String)
    time = sqlalchemy.Column(sqlalchemy.String)

    def __repr__(self):
        return f"Intervals(id={self.id}, interval={self.interval}, time={self.time})"

    class Api_add(BaseModel):
        interval: str
        time: str

        def add_interval(interval, time):
            try:
                interval = Intervals(interval=interval, time=time)
                session.add(interval)
                session.commit()
                return interval
            except Exception as error:
                session.flush()
                session.rollback()
                return None

    class Api_list(BaseModel):
        interval: str

        def get_interval(id):
            interval = session.query(Intervals).filter_by(id=id).first()
            return interval

        def get_all_intervals():
            interval = session.query(Intervals).all()
            return interval

    class Api_delete(BaseModel):
        interval: str

        def delete_interval(interval):
            interval = session.query(Intervals).filter_by(interval=interval).first()
            session.delete(interval)
            session.commit()
            return interval

    def create_intervals():
        intervals = ['Diário', 'Semanal', 'Mensal', '5 Dias', '10 Dias', '15 Dias']
        # time in seconds
        time = [86400, 604800, 2592000, 432000, 864000, 1296000]
        for interval, time in zip(intervals, time):
            try:
                interval = Intervals(interval=interval, time=time)
                session.add(interval)
                session.commit()
            except Exception as error:
                session.flush()
                session.rollback()
                return None


class Days(Base):
    __tablename__ = 'days'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    day = sqlalchemy.Column(sqlalchemy.String, unique=True)

    def __repr__(self):
        return f"Days(id={self.id}, day={self.day})"

    class Api_list(BaseModel):
        day: str

        def get_day(day):
            day = session.query(Days).filter_by(day=day).first()
            return day

        def get_all_days():
            day = session.query(Days).all()
            return day

    # crie todos os dias da semana
    def create_days():
        days = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        for day in days:
            day = Days(day=day)
            session.add(day)
            session.commit()
        return day

class Backups_types(Base):
    __tablename__ = 'backups_types'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    backup_type = sqlalchemy.Column(sqlalchemy.String, unique=True)

    def __repr__(self):
        return f"Backups_types(id={self.id}, backup_type={self.backup_type})"

    class Api_list(BaseModel):
        backup_type: str

        def get_backup_type(backup_type):
            backup_type = session.query(Backups_types).filter_by(backup_type=backup_type).first()
            return backup_type

        def get_all_backups_types():
            backup_type = session.query(Backups_types).all()
            return backup_type

    def create_backups_types():
        backups_types = ['Full', 'Incremental']
        for backup_type in backups_types:
            backup_type = Backups_types(backup_type=backup_type)
            session.add(backup_type)
            session.commit()
        return backup_type


class Backups_jobs(Base):
    __tablename__ = 'backups_jobs'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    backup_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('backups.id'))
    backup_log = sqlalchemy.Column(sqlalchemy.String)
    backup_next = sqlalchemy.Column(sqlalchemy.DateTime)
    backup_last = sqlalchemy.Column(sqlalchemy.DateTime)
    backup_interval = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('intervals.id'))
    backup_status = sqlalchemy.Column(sqlalchemy.String)
    backup_log_file = sqlalchemy.Column(sqlalchemy.String)

    def __repr__(self):
        return f"Backups_jobs(id={self.id}, backup_id={self.backup_id}, backup_log={self.backup_log}, backup_next={self.backup_next}, backup_last={self.backup_last}, backup_interval={self.backup_interval}, backup_status={self.backup_status}, backup_log_file={self.backup_log_file})"

    class Api_list(BaseModel):
        backup_id: str

        def get_backup_job(backup_id):
            backup_job = session.query(Backups_jobs).filter_by(backup_id=backup_id).first()
            return backup_job

        def get_all_backups_jobs():
            backup_job = session.query(Backups_jobs).all()
            return backup_job

    class Api_create(BaseModel):
        backup_id: str
        backup_log: str
        backup_next: str
        backup_last: str
        backup_interval: str
        backup_status: str
        backup_log_file: str

        def add_backup_job(backup_id, backup_log, backup_next, backup_last, backup_interval, backup_status, backup_log_file):
            try:
                backup_job = Backups_jobs(backup_id=backup_id, backup_log=backup_log, backup_next=backup_next, backup_last=backup_last, backup_interval=backup_interval, backup_status=backup_status, backup_log_file=backup_log_file)
                session.add(backup_job)
                session.commit()
                return backup_job
            except Exception as error:
                session.flush()
                session.rollback()
                return error

Base.metadata.create_all(engine)

def check_user_type(username):
    user = session.query(Users).filter_by(username=username).first()
    if user is None:
        return None
    else:
        return user.type

def check_user_exists(username):
    user = session.query(Users).filter_by(username=username).first()
    if user is None:
        return False
    else:
        return True

def check_username_with_token(token):
    token = session.query(Token).filter_by(token=token).first()
    if token is None:
        return None
    else:
        return token.username

def check_admin_with_token(token: str):
    token = session.query(Token).filter_by(token=token).first()
    user = session.query(Users).filter_by(username=token.username).first()
    if token is None:
        return HTTPException(status_code=401, detail="Not authorized")
    elif user.type == 'admin':
        return True
    else:
        raise HTTPException(status_code=401, detail="Not authorized")

def check_user_autorized(username):
    user = session.query(Users).filter_by(username=username).first()
    if user.autorized == True:
        return True
    else:
        return False

if Config.check_config('api_url') is None:
    config = configparser.ConfigParser()
    config.read('config.ini')
    api_url = config['FASTAPI']['api_url']
    Config.create_config('api_url', api_url, 'URL do FASTAPI', 'admin')

if  session.query(Users).filter_by(username="admin").first() == None:
    admin = Users(username='admin', password=hash_password('admin'), type='admin',email="pedroluizmossi@gmail.com", autorized=True)
    session.add(admin)
    session.commit()

if Days.Api_list.get_all_days() == []:
        Days.create_days()

if Intervals.Api_list.get_all_intervals() == []:
        Intervals.create_intervals()

if Backups_types.Api_list.get_all_backups_types() == []:
        Backups_types.create_backups_types()

def print_hello():
    print('Hello World')



