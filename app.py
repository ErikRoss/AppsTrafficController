# ----------------------------------------------------------------------------#
# Imports
# ----------------------------------------------------------------------------#
import datetime
from functools import wraps

from flask import Flask, render_template, request, session, flash, redirect, url_for
import logging
from logging import Formatter, FileHandler

from flask_cors import CORS
from flask_login import LoginManager, current_user, login_user, logout_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.file import FileField
from werkzeug.datastructures import CombinedMultiDict
from werkzeug.utils import secure_filename

from forms import AddAppForm, AddCampaignForm, LoginForm, RegisterForm, ForgotForm
from tables import AppsTable
import os


# ----------------------------------------------------------------------------#
# App Config.
# ----------------------------------------------------------------------------#

app = Flask(__name__)
app.config.from_object('config')
CORS(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)


# Automatically tear down SQLAlchemy.
@app.teardown_request
def shutdown_session(exception=None):
    db.session.remove()


from models import Campaign, User, App, Domain


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# Login required decorator.
def login_required(test):
    @wraps(test)
    def wrap(*args, **kwargs):
        if current_user.is_authenticated:
            return test(*args, **kwargs)
        else:
            flash('You need to login first.')
            return redirect(url_for('login'))

    return wrap


# ----------------------------------------------------------------------------#
# Controllers.
# ----------------------------------------------------------------------------#


@app.route('/', methods=['GET'])
def home():
    domain = request.args.get('domain')
    redirect_domain = Domain.query.filter_by(domain=domain).first()
    if redirect_domain:
        campaign_hash_code = request.args.get('campaign')
        if campaign_hash_code:
            campaign = Campaign.query.filter_by(hash_code=campaign_hash_code).first()
            return render_template(
                'pages/placeholder.home.html', 
                redirect_domain=redirect_domain, 
                campaign=campaign)
        
    if 'logged_in' in session:
        return render_template('pages/placeholder.home.html')
    else:
        flash('You need to login first.')
        return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        if username and password:
            user = User.query.filter_by(username=username).first()
            if user and user.password == password:
                session['logged_in'] = True
                session['user_id'] = user.id
                login_user(user)
                flash('Authorized successfully.')
                return redirect(url_for('home'))
            else:
                flash('Wrong username or password.')
                form = LoginForm(request.form)
                return render_template('forms/login.html', form=form)
        else:
            flash('Wrong username or password.')
            form = LoginForm(request.form)
            return render_template('forms/login.html', form=form)
    else:
        if current_user.is_authenticated:
            flash('Already logged in.')
            return redirect(url_for('home'))
        else:
            form = LoginForm()
            return render_template('forms/login.html', form=form)


@login_required
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    logout_user()
    flash('Logged out successfully.')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm = request.form.get("confirm")
        if username and email and password and confirm:
            if password == confirm:
                user = User.query.filter_by(username=username).first()
                if user:
                    flash('Username already exists.')
                    form = RegisterForm(request.form)
                    return render_template('forms/register.html', form=form)
                else:
                    user = User(username=username, password=password, email=email)
                    db.session.add(user)
                    db.session.commit()
                    flash('Registered successfully.')
                    return redirect(url_for('login'))
            else:
                flash('Passwords must match.')
                form = RegisterForm(request.form)
                return render_template('forms/register.html', form=form)
        else:
            flash('Please fill in all the fields.')
            form = RegisterForm(request.form)
            return render_template('forms/register.html', form=form)
    else:
        form = RegisterForm(request.form)
        return render_template('forms/register.html', form=form)


@app.route('/forgot')
def forgot():
    form = ForgotForm(request.form)
    return render_template('forms/forgot.html', form=form)


def save_app_image(image: FileField):
    file_name = image.data.filename
    now_time = int(str(datetime.datetime.now().timestamp()).replace(".", ""))
    file_extension = str(file_name).split(".")[-1]
    image_name = f'{now_time}.{file_extension}'
    image_path = f'{app.config["UPLOAD_FOLDER"]}/{image_name}'
    
    image.data.save(image_path)
    
    return image_name


@login_required
@app.route('/apps', methods=['GET', 'POST'])
def apps():
    if request.method == 'POST':
        if 'logged_in' in session:
            form = AddAppForm(CombinedMultiDict((request.files, request.form)))
            app_title = form.title.data
            app_url = form.url.data
            app_image = form.image
            app_operating_system = form.operating_system.data
            app_tags = form.tags.data
            app_unique_tag = form.unique_tag.data
            app_description = form.description.data
            app_status = form.status.data
            app_parameters = [
                app_title, 
                app_url, 
                app_image, 
                app_operating_system, 
                app_unique_tag,
                app_status
                ]

            if all(app_parameters):
                app_image = save_app_image(app_image)
                new_app = App(
                    title=app_title, 
                    url=app_url, 
                    image=app_image, 
                    operating_system=app_operating_system,
                    tags=app_tags, 
                    unique_tag=app_unique_tag, 
                    description=app_description,
                    status=app_status
                    )
                db.session.add(new_app)
                db.session.commit()
                flash('App added successfully.')
                form = AddAppForm()
                return render_template('forms/add_app.html', form=form)
            else:
                flash('Please fill in all the fields.')
                form = AddAppForm()
                return render_template('forms/add_app.html', form=form)
        else:
            flash('You need to login first.')
            form = LoginForm()
            return render_template('forms/login.html', form=form)
    else:
        form = AddAppForm()
        
        app_query = App.query.all()
        app_rows = []
        for app_obj in app_query:
            img_html = f'<img src="{url_for("static", filename=f"img/uploads/{app_obj.image}")}"></img>'
            app_rows.append({
                'id': app_obj.id,
                'title': app_obj.title,
                'url': app_obj.url,
                'image': img_html,
                'operating_system': app_obj.operating_system,
                'tags': app_obj.tags,
                'unique_tag': app_obj.unique_tag,
                'description': app_obj.description,
                'status': app_obj.status
                })
        table = AppsTable(app_rows)

        return render_template('forms/add_app.html', form=form, table=table)


@login_required
@app.route('/campaigns', methods=['GET', 'POST'])
def campaigns():
    if request.method == 'GET':
        apps = App.query.all()
        app_choices = [(app.id, app.title) for app in apps]
        
        form = AddCampaignForm()
        form.apps.choices = app_choices
        
        campaigns_query = Campaign.query.all()
        campaigns_rows = []
        for campaign_obj in campaigns_query:
            campaigns_rows.append({'id': campaign_obj.id,
                                   'title': campaign_obj.title,
                                   'description': campaign_obj.description,
                                   'geo': campaign_obj.geo,
                                   'apps': ', '.join([app.title for app in campaign_obj.apps]),
                                   'custom_parameters': campaign_obj.custom_parameters,
                                   'hash_code': campaign_obj.hash_code})
        table = AppsTable(campaigns_rows)
        
        return render_template('forms/add_campaign.html', form=form, campaigns_table=table)
    else:
        form = AddCampaignForm(request.form)
        campaign_title = form.title.data
        campaign_description = form.description.data
        campaign_geo = form.geo.data
        campaign_apps = form.apps.data
        campaign_custom_parameters = form.custom_parameters.data
        
        campaign_parameters = [
            campaign_title,
            campaign_geo,
            campaign_apps,
            ]
        
        if campaign_description is None:
            campaign_description = ''
            
        if campaign_custom_parameters is None:
            campaign_custom_parameters = ''
        
        if all(campaign_parameters):
            new_campaign = Campaign(
                title=campaign_title,
                description=campaign_description,
                user=current_user.id,
                geo=campaign_geo,
                custom_parameters=campaign_custom_parameters,
                apps=[campaign_apps]
                )
            db.session.add(new_campaign)
            db.session.commit()
            flash('Campaign added successfully.')
            return redirect(url_for('campaigns'))

# Test routes

@app.route('/get_test', methods=['GET'])
def get_test():
    """ Test route for GET requests, returns a JSON response. """
    return {
        'system': ['Linux', 'Windows', 'Mac', 'Android', 'iOS'],
        'browsers': ['Chrome', 'Firefox', 'Safari', 'Opera', 'Edge', 'IE', 'Other']
        }
    

@app.route('/post_test', methods=['POST'])
def post_test():
    """ Test route for POST requests, returns a JSON response with the result of the request. """
    try:
        print(request.json)
        print(request.data)
        print(request.form)
        test_parameters = request.json
        name = test_parameters['name']
        age = test_parameters['age']
        system = test_parameters['system']
        browsers = test_parameters['browsers']
        custom_parameters = test_parameters['custom_parameters']
    except KeyError:
        return {'result': 'error'}
    else:
        return {
            'result': 'success',
            'data': {
                'name': name,
                'age': age,
                'system': system,
                'browsers': browsers,
                'custom_parameters': custom_parameters
                }
            }

    d = {
    'name': 'John Doe',
    'age': 16,
    'system': 'Linux',
    'browsers': [
        'Chrome', 
        'Firefox'
        ],
    'custom_parameters': {
        'param1': 'value1',
        'param2': 'value2'
        }
    }

# Error handlers.

@app.errorhandler(500)
def internal_error(error):
    # db_session.rollback()
    return render_template('errors/500.html'), 500


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404


if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

# ----------------------------------------------------------------------------#
# Launch.
# ----------------------------------------------------------------------------#

# Default port:
if __name__ == '__main__':
    db.create_all()
    app.run(cors_allowed_origins=["http://localhost:3000", "*"])

# Or specify port manually:
'''
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''
