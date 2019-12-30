import pygame, os
from flask import render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from flask.ext.admin import Admin, BaseView, expose
from flask.ext.admin.contrib.sqla import ModelView
from flask.ext.admin.contrib.fileadmin import FileAdmin
from app import app, db, lm, oid, admin
from config import TAGMAP
from forms import LoginForm, EditForm
from models import *
from sqlalchemy.orm.exc import UnmappedInstanceError
from datetime import datetime, timedelta
from decorators import async
from config import basedir
from wtforms.fields import SelectField
from Queue import Queue
import glob

pygame.mixer.init()
fxchannel=pygame.mixer.Channel(1)
clock = pygame.time.Clock()




          
_theme_queue=Queue()
@async
def entrance_queue(theme):
	global _theme_queue
	controller=False
	if _theme_queue.empty():
		controller=True
	_theme_queue.put(theme)
	print "added %s to queue" % theme
	if controller:
		while pygame.mixer.music.get_busy():
			clock.tick(10)
		if _theme_queue.empty()==False and pygame.mixer.music.get_busy() ==False:
			pygame.mixer.music.load(_theme_queue.get().filename)
			_theme_queue.task_done()
		while _theme_queue.empty()==False:
			pygame.mixer.music.queue(_theme_queue.get().filename)
			_theme_queue.task_done()
		#somehow turn xbmc music down
		pygame.mixer.music.play()

				
"""
resume_volume() # somehow set the xbmc volume back up

@async
def resume_volume():
	#probably using pygame.music.set_endevent
"""



@app.before_request
def before_request():
	g.user = current_user
	if g.user.is_authenticated:
		g.user.last_seen = datetime.utcnow()
		try:
			db.session.add(g.user._get_current_object())
			db.session.commit()
		except UnmappedInstanceError as e:
			print(e)

@app.route("/")
def index():
	global TAGMAP
	tags = [item for sublist in list(reversed(zip(*[iter(TAGMAP)]*4))) for item in sublist]
	tagsandsounds=[{'category':x, 
		'sounds':[
			{'file': y.filename, 'name':y.name} for y in sorted(x.sounds,key=lambda x:x.name)]
		} for x in db.session.query(Tag).order_by(Tag.name).all() ]
	return render_template('soundboard.html', tags=tags, filenamesandcategories=tagsandsounds, jqueryurl=url_for('static', filename='js/jquery.min.js'))

@app.route('/load')
def loadsounds():


	soundfilenames = glob.glob('sounds/*.wav')
	soundfilenames.extend(glob.glob('sounds/*.mp3'))
	print "sounds/*.wav+mp3: %s"% str(soundfilenames)


	for filename in soundfilenames:
		afile=get_or_create(Sound, filename=filename)

	themefilenames = glob.glob('themes/*.wav')
	themefilenames.extend(glob.glob('themes/*.mp3'))

	for filename in themefilenames:
		afile=get_or_create(ThemeSong, filename=filename)

	soundfilenames = glob.glob('sounds/*/*.wav')
	soundfilenames.extend(glob.glob('sounds/*/*.mp3'))

	for f in soundfilenames:
		newname=os.path.join('sounds',os.path.basename(f))
		print newname
		tagname=os.path.relpath(os.path.dirname(f),'sounds')
		tag=get_or_create(Tag, name=tagname)
		os.rename(f,newname)
		asound=get_or_create(Sound, filename=newname)
		if tag not in asound.tags:
			asound.tags.append(tag)
			db.session.commit()
	return "ok"

@app.route("/play/sounds/<name>")
def play(name):
	global fxchannel
	name=os.path.join('sounds', name)
	#print name
	if not pygame.mixer.get_init():
		pygame.mixer.init();
	fxchannel.play(pygame.mixer.Sound(name))
	#pygame.mixer.music.load(name)
	#pygame.mixer.music.play()
	##sounds[name].play()
	return "ok"
	
@app.route("/play/tag/<tagname>")
def playtag(tagname):
	'''
	if not pygame.mixer.get_init():
		pygame.mixer.init();
	
	if (tagname != playtag.lasttag) or  (datetime.utcnow() > (playtag.lasttagtime + timedelta(seconds=2))):
		if tagname == 'random':
			tag = Tag.query.order_by(func.random()).first()
		else:
			tag = get_or_create(Tag, name=tagname);
		filetoplay=tag.randomsound().filename
		playtag.lasttag = tagname
		playtag.lasttagfilename = filetoplay
		playtag.lasttagtime = datetime.utcnow()
	else:
		filetoplay = playtag.lasttagfilename
		playtag.lasttagtime = datetime.utcnow()

	#print filetoplay

	fxchannel.play(pygame.mixer.Sound(filetoplay))
	return filetoplay
	'''
	if g.user is not None and g.user.is_authenticated:
		source = g.user.nickname
	else:
		source = 'anonymous'
	return playtagunwrapped(tagname,source)


def playtagunwrapped(tagname,source):
	global fxchannel	
	if not pygame.mixer.get_init():
		pygame.mixer.init();
	
	if source in playtagunwrapped.sources:
		if (tagname != playtagunwrapped.lasttag[source]) or  (datetime.utcnow() > (playtagunwrapped.lasttagtime[source] + timedelta(seconds=3))):
			if tagname == 'random':
				tag = Tag.query.order_by(func.random()).first()
			else:
				tag = get_or_create(Tag, name=tagname);
			filetoplay=tag.randomsound().filename
			playtagunwrapped.lasttag[source] = tagname
			playtagunwrapped.lasttagfilename[source] = filetoplay
			playtagunwrapped.lasttagtime[source] = datetime.utcnow()
		else:
			filetoplay = playtagunwrapped.lasttagfilename[source]
			playtagunwrapped.lasttagtime[source] = datetime.utcnow()
	else:
		if tagname == 'random':
			tag = Tag.query.order_by(func.random()).first()
		else:
			tag = get_or_create(Tag, name=tagname);
		filetoplay=tag.randomsound().filename
		playtagunwrapped.sources.append(source)
		playtagunwrapped.lasttag[source]=tagname
		playtagunwrapped.lasttagfilename[source]=filetoplay
		playtagunwrapped.lasttagtime[source]=datetime.utcnow()
	#print filetoplay

	fxchannel.play(pygame.mixer.Sound(filetoplay))
	return filetoplay
playtagunwrapped.sources=[]
playtagunwrapped.lasttag={}
playtagunwrapped.lasttagfilename={}
playtagunwrapped.lasttagtime={}

@app.route('/login', methods = ['GET', 'POST'])
@oid.loginhandler
def login():
	if g.user is not None and g.user.is_authenticated:
		return redirect(url_for('index'))
	form = LoginForm()
	if form.validate_on_submit():
		session['remember_me'] = form.remember_me.data
		return oid.try_login(form.openid.data, ask_for = ['nickname', 'email'])
	return render_template('login.html', 
		title = 'Sign In',
		form = form,
		providers = app.config['OPENID_PROVIDERS'])

@oid.after_login
def after_login(resp):
	if resp.email is None or resp.email == "":
		flash('Invalid login. Please try again.')
		return redirect(url_for('login'))
	user = User.query.filter_by(email = resp.email).first()
	if user is None:
		nickname = resp.nickname
		if nickname is None or nickname == "":
			nickname = resp.email.split('@')[0]
		nickname= User.make_unique_nickname(nickname)
		user = User(nickname = nickname, email = resp.email, urole = "USER")
		user.theme = ThemeSong.random_themesong()
		db.session.add(user)
		db.session.commit()
	remember_me = False
	if 'remember_me' in session:
		remember_me = session['remember_me']
		session.pop('remember_me', None)
	
	if user.hastheme():
		entrance_queue(user.theme)
	login_user(user, remember = remember_me)
	return redirect(request.args.get('next') or url_for('index'))

@lm.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route('/logout')
def logout():
	logout_user()
	return redirect(url_for('index'))

@app.route('/user/<nickname>')
@login_required
def user(nickname):
	user = User.query.filter_by(nickname = nickname).first()
	if user == None:
		flash('User ' + nickname + ' not found.')
		return redirect(url_for('index'))
	posts = [
		{ 'author': user, 'body': 'Test post #1' },
		{ 'author': user, 'body': 'Test post #2' }
	]
	return render_template('user.html',
		user = user,
		posts = posts)

@app.route('/edit', methods = ['GET', 'POST'])
@login_required
def edit():
    form = EditForm()
    if form.validate_on_submit():
        g.user.nickname = form.nickname.data
        g.user.theme = form.themesong.data
        db.session.add(g.user)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit'))
    else:
        form.nickname.data = g.user.nickname
        form.themesong.data = g.user.theme
    return render_template('edit.html',
        form = form)

class SoundModelView(ModelView):
	column_display_all_relations=True
	column_list = ('name', 'tags')
	form_excluded_columns = ('name')
	
	def is_accessible(self):
		if g.user.is_authenticated and g.user.is_admin:
			return True
		else:
			return False
	def on_model_change(self, form, model, is_created):
		

		if is_created==True:
			model.name=stripfilename(model.filename)
		self.session.add(model)

class ThemeSongModelView(ModelView):
	#column_display_all_relations=True
	column_list = ('name', 'users')
	form_excluded_columns = ('name')
	def is_accessible(self):
		if g.user.is_authenticated and g.user.is_admin:
			return True
		else:
			return False
	def on_model_change(self, form, model, is_created):
		

		if is_created==True:
			model.name=stripfilename(model.filename)
		self.session.add(model)

class SoundFileAdmin(FileAdmin):
	allowed_extensions=('wav', 'mp3', 'ogg')
	def is_accessible(self):
		if g.user.is_authenticated and g.user.is_admin:
			return True
		else:
			return False
	def on_file_upload(self, directory, path, filename):
		db.session.add(Sound(filename=filename))
		db.session.commit()

class ThemeSongFileAdmin(FileAdmin):
	allowed_extensions=('wav', 'mp3', 'ogg')
	def is_accessible(self):
		if g.user.is_authenticated and g.user.is_admin:
			return True
		else:
			return False
	def on_file_upload(self, directory, path, filename):
		db.session.add(ThemeSong(filename=filename))
		db.session.commit()
class UserModelView(ModelView):
	can_create=False
	form_overrides = dict(status=SelectField)
	form_args = dict(
		urole=dict(
			choices=[(0,"USER"), (1,"admin")]))
	def is_accessible(self):
		if g.user.is_authenticated and g.user.is_admin:
			return True
		else:
			return False
admin.add_view(SoundModelView(Sound, db.session))
admin.add_view(ThemeSongModelView(ThemeSong, db.session, name="Theme Songs"))
admin.add_view(ModelView(Tag, db.session))
admin.add_view(UserModelView(User, db.session))
admin.add_view(SoundFileAdmin(os.path.join(basedir, 'sounds'), '/sounds/', name = 'Upload Sounds'))
admin.add_view(ThemeSongFileAdmin(os.path.join(basedir, 'themes'), '/themes/', name = 'Upload Theme Songs'))
