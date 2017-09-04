import base64
import os
import random
import subprocess
import sqlite3
import uuid

import logging as log

import pandas as pd

from flask import Flask, redirect, render_template,\
    request, url_for
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename

from PIL import Image as pil_image
from PIL.ExifTags import TAGS, GPSTAGS

from .models import FishPic
from .sqlite_queue import SqliteQueue

log.basicConfig(level=log.DEBUG)


# Flask extensions
bootstrap = Bootstrap()


app = Flask(__name__)


# Initialize flask extensions
bootstrap.init_app(app)


log.basicConfig(level=log.DEBUG)


# env vars for tmp purposes
class Config(object):
    # DEBUG = False
    # TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY',
                                'superSecretDoNotUseOnOpenWeb')


# init config
app.config.from_object(Config)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/legal')
def legal():
    return render_template('legal.html')


@app.route('/regulations')
def regulations():
    return render_template('regulations.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # TODO: add data validation step
        if True:
            log.debug('data:')
            log.debug(request.data)
            log.debug('files:')
            log.debug(request.files)
            fish_pic_file = request.files['fish-pic-input']
            # TODO: path should be updated before production
            dump_path = os.path.join('data',
                                     'fish_pics')
            dump_path_sm = os.path.join('data',
                                        'fish_pics_sm')
            log.debug('dump_path:')
            log.debug(os.listdir(dump_path))
            # fish_pic_ext = (secure_filename(fish_pic_file.filename)
            #                 .split('.')[-1])
            fish_pic_ext = 'jpg'

            # reading into PIL
            log.debug('Reading PIL: %s', fish_pic_file.filename)
            img = pil_image.open(fish_pic_file)

            # Extract lat lon from Image if present
            img_exif = get_exif_data(img)
            img_lat_lon = get_lat_lon(img_exif)
            log.debug('Lat: %s', img_lat_lon[0])
            log.debug('Lon: %s', img_lat_lon[1])

            # get a random uuid to use for filename
            fish_pic_uuid = uuid.uuid4()

            fish_pic_name = '{}.{}'.format(fish_pic_uuid,
                                           fish_pic_ext)

            fish_pic_path = os.path.join(dump_path,
                                         fish_pic_name)

            fish_pic_path_sm = os.path.join(dump_path_sm,
                                            fish_pic_name)

            log.debug('Saving: %s', fish_pic_path)

            # TODO: resize and convert to jpg on save
            # fish_pic_file.save(fish_pic_path)
            img.save(fish_pic_path)
            # save thumbnail version
            mc = 300
            if img.size[0] > img.size[1]:
                wh_tuple = (mc, img.size[1] * mc // img.size[0])
            else:
                wh_tuple = (img.size[0] * mc // img.size[1], mc)

            img_sm = img.resize(wh_tuple)
            img_sm.save(fish_pic_path_sm)

            img_path = os.path.abspath(fish_pic_path)
            img_path_sm = os.path.abspath(fish_pic_path_sm)

            # add submission to database
            # TODO: make an ENV var
            fish_pic_db = FishPic('data/dbs/fishr.db')
            fish_pic_id = fish_pic_db.append({'img_path': img_path,
                                              'img_path_sm': img_path_sm,
                                              'latitude': img_lat_lon[0],
                                              'longitude': img_lat_lon[1]})

            # push to scoring queue
            # TODO: make queue path a global in ENV
            log.debug('Push queue: %s', fish_pic_path)
            fish_pic_queue = SqliteQueue('data/queues/fish_pic_queue.db')
            fish_pic_queue.append((fish_pic_id, img_path))

            return redirect(url_for('loading_splash',
                                    fish_pic_id=fish_pic_id))

    # TODO: refactor this block
    # art for photo upload page
    art_sel = 'CameraIconSmall.png'
    art_url = url_for('static',
                      filename='{}/{}'.format('images',
                                              art_sel))

    # if not a post request return html
    return render_template('upload.html',
                           art_url=art_url)


def get_fish_pic_dict(fish_pic_id):
    # function is used to "gin up" the real/fake result data
    # return None if scoring is not finished
    # else return the entire fish_pic_dict dump

    # TODO: refactor to ENV global
    fish_pic_db = FishPic('data/dbs/fishr.db')
    fish_pic_dict = fish_pic_db.get(fish_pic_id)
    log.debug('fish_pic_dict: %s', fish_pic_dict)

    species_pred = fish_pic_dict.get('species_pred')

    if not species_pred:
        # TODO: refactor this to get a true get dict fxn or rename
        # return null data until scoring job finishes
        return fish_pic_dict

    else:

        confidence = round(max(fish_pic_dict.get('y_pred')), 2) * 100

        species_to_invasive = {'black_bullhead': False,
                               'black_crappie': False,
                               'black_redhorse': False,
                               'bluegill': False,
                               'carp': True,
                               'channel_catfish': False,
                               'largemouth_bass': False,
                               'northern_pike': False,
                               'pumpkinseed_sunfish': False,
                               'rainbow_trout': False,
                               'smallmouth_bass': False,
                               'smallmouth_buffalo': False,
                               'walleye': False,
                               'white_bass': False,
                               'white_crappie': False,
                               'white_perch': True,
                               'yellow_perch': False}

        results = {'invasive': species_to_invasive[species_pred],
                   'species': species_pred,
                   'length': 8,
                   'confidence': confidence}

        fish_pic_dict['results'] = results

        # TODO: refactor this to seperate function
        # save the calcs from this function to DB
        fish_pic_db.replace(fish_pic_id, fish_pic_dict)
        log.info('Commited to DB: %s', fish_pic_dict)

        return fish_pic_dict

def get_exif_data(image):
    """Returns a dictionary from the exif data of an PIL Image item. Also converts the GPS Tags"""
    exif_data = {}
    info = image._getexif()
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                gps_data = {}
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_data[sub_decoded] = value[t]

                exif_data[decoded] = gps_data
            else:
                exif_data[decoded] = value

    return exif_data

def _get_if_exist(data, key):
    if key in data:
        return data[key]
    return None

def _convert_to_degress(value):
    """Helper function to convert the GPS coordinates stored in the EXIF to degress in float format"""
    d0 = value[0][0]
    d1 = value[0][1]
    d = float(d0) / float(d1)

    m0 = value[1][0]
    m1 = value[1][1]
    m = float(m0) / float(m1)

    s0 = value[2][0]
    s1 = value[2][1]
    s = float(s0) / float(s1)

    return d + (m / 60.0) + (s / 3600.0)

def get_lat_lon(exif_data):
    """Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)"""
    lat = None
    lon = None

    if "GPSInfo" in exif_data:
        gps_info = exif_data["GPSInfo"]

        gps_latitude = _get_if_exist(gps_info, "GPSLatitude")
        gps_latitude_ref = _get_if_exist(gps_info, 'GPSLatitudeRef')
        gps_longitude = _get_if_exist(gps_info, 'GPSLongitude')
        gps_longitude_ref = _get_if_exist(gps_info, 'GPSLongitudeRef')
        print(gps_latitude, gps_longitude)
        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
            lat = _convert_to_degress(gps_latitude)
            if gps_latitude_ref != "N":
                lat = 0 - lat

            lon = _convert_to_degress(gps_longitude)
            if gps_longitude_ref != "E":
                lon = 0 - lon

    return lat, lon

@app.route('/loading_splash/<int:fish_pic_id>')
def loading_splash(fish_pic_id):
    fish_pic_dict = get_fish_pic_dict(fish_pic_id)
    # TODO: what if model results are never returned
    if not fish_pic_dict.get('species_pred'):
        # random loading art
        art_sel = random.choice(ART_IDX['loading'])
        art_url = url_for('static',
                          filename='{}/{}'.format('images',
                                                  art_sel))

        # return the loading page if model results are None
        return render_template('loading_splash.html',
                               fish_pic_id=fish_pic_id,
                               art_url=art_url)
    else:
        # if model results are availible redirect
        return redirect(url_for('submission_results',
                                fish_pic_id=fish_pic_id))


ART_IDX = {'keeper': ['GoodFish1Small.png',
                      'GoodFish2Small.png',
                      'GoodFish3Small.png',
                      'GoodFish4Small.png'],
           'release': ['ReleaseFish1Small.png',
                       'ReleaseFish2Small.png',
                       'ReleaseFish3Small.png'],
           'invasive': ['BadFish1Small.png',
                        'BadFish2Small.png',
                        'BadFish3Small.png'],
           'loading': ['Loading1Small.png',
                       'Loading2Small.png',
                       'Loading3Small.png',
                       'Loading4Small.png'],
           'black_bullhead': 'black_bullhead.png',
           'black_crappie': 'black_crappie.jpeg',
           'black_redhorse': 'black_redhorse.jpeg',
           'bluegill': 'bluegill.jpeg',
           'carp': 'carp.jpeg',
           'channel_catfish': 'channel_catfish.jpeg',
           'largemouth_bass': 'largemouth_bass.png',
           'northern_pike': 'northern_pike.jpeg',
           'pumpkinseed_sunfish': 'pumpkinseed_sunfish.jpeg',
           'rainbow_trout': 'rainbow_trout.jpeg',
           'smallmouth_bass': 'smallmouth_bass.png',
           'smallmouth_buffalo': 'smallmouth_buffalo.jpeg',
           'walleye': 'walleye.png',
           'white_bass': 'white_bass.jpeg',
           'white_crappie': 'white_crappie.jpeg',
           'white_perch': 'white_perch.jpeg',
           'yellow_perch': 'yellow_perch.jpeg'}


@app.route('/cdn_fish_pic/<int:fish_pic_id>')
@app.route('/cdn_fish_pic/<int:fish_pic_id>.jpg')
def cdn_fish_pic(fish_pic_id):
    fish_pic_dict = get_fish_pic_dict(fish_pic_id)
    log.debug('fish_pic_dict: %s', fish_pic_dict)

    img_path = fish_pic_dict['img_path']

    with open(img_path, 'rb') as f:
        fish_pic_file = f.read()

    return fish_pic_file, 200, {'Content-Type': 'image/jpg'}


@app.route('/cdn_fish_pic_sm/<int:fish_pic_id>')
@app.route('/cdn_fish_pic_sm/<int:fish_pic_id>.jpg')
def cdn_fish_pic_sm(fish_pic_id):
    fish_pic_dict = get_fish_pic_dict(fish_pic_id)
    log.debug('fish_pic_dict: %s', fish_pic_dict)

    img_path = fish_pic_dict['img_path_sm']

    with open(img_path, 'rb') as f:
        fish_pic_file = f.read()

    return fish_pic_file, 200, {'Content-Type': 'image/jpg'}


@app.route('/label', methods=['GET', 'POST'])
def label():
    # TODO: refactor to ENV
    fish_pic_db = FishPic('data/dbs/fishr.db')

    if request.method == 'POST':
        log.debug('label form: %s', request.form)

        fish_pic_id = request.form.get('fish_pic_id', type=int)
        fish_label = request.form.get('fish_label')

        # TODO: update to a transactional vs no-sql setup
        log.debug('fish_pic_id: %s', fish_pic_id)
        fish_pic_dict = fish_pic_db.get(fish_pic_id)
        try:
            fish_pic_dict['fish_labels'].append(fish_label)
        except KeyError:
            fish_pic_dict['fish_labels'] = [fish_label]

        fish_pic_db.replace(fish_pic_id, fish_pic_dict)
        log.info('Commit to DB: %s', fish_pic_dict)

        return '', 200

    # get a fish_pic for them to label
    fish_pic_id, fish_pic_dict = fish_pic_db.random()

    try:
        species_pred = fish_pic_dict['species_pred']
    except:
        # TODO: refactor this in a more robust way to have unknown class
        # if the image grab fails to grab an image with a pred
        species_pred = 'unknown'

    return render_template('label.html',
                           fish_pic_id=fish_pic_id,
                           species_pred=species_pred)


def get_rules(state, species):
    rules_df = pd.read_csv('fishr/tmp_fishing_rules.csv')
    out = rules_df[rules_df['state'] == state]
    species_mask = out['species'].str.contains(species)

    if species_mask.sum() > 0:
        out = out[species_mask]

    return out


@app.route('/submission_results/<int:fish_pic_id>')
def submission_results(fish_pic_id):
    fish_pic_dict = get_fish_pic_dict(fish_pic_id)

    # redirect if user inputs non existant key
    if not fish_pic_dict:
        return redirect(url_for('index'))

    results = fish_pic_dict['results']

    # TODO: refactor this into lookup functions
    # based on state rules database(s).
    if results['invasive']:
        catch_type = 'invasive'
    else:
        if int(fish_pic_id) % 2 == 0:
            catch_type = 'keeper'
        else:
            catch_type = 'release'

    results_heading_dict = {
        'invasive': 'Invasive Species: Don\'t release',
        'keeper': 'This Catch is a Keeper',
        'release': 'Please Release this Fish'
    }

    species_pred = results['species']
    confidence = results['confidence']

    # the heading is the bold message displayed to user
    results_heading = results_heading_dict[catch_type]

    art_sel = ART_IDX[species_pred]

    # bonus art for action they should take
    art_action = random.choice(ART_IDX[catch_type])

    log.debug('art_sel: %s', art_sel)
    art_url = url_for('static',
                      filename='{}/{}'.format('images',
                                              art_sel))

    art_action_url = url_for('static',
                             filename='{}/{}'.format('images',
                                                     art_action))

    # get fishing regulation for this slice
    rules_html = get_rules('ohio', species_pred).to_html(index=False)

    return render_template('submission_results.html',
                           results_heading=results_heading,
                           species_pred=species_pred,
                           confidence=confidence,
                           art_url=art_url,
                           art_action_url=art_action_url,
                           rules_html=rules_html,
                           fish_pic_id=fish_pic_id)

@app.route('/download_cache')
def download_cache():
    return render_template('download_cache.html')


@app.route('/download_cache_all.csv')
def download_cache_all_csv():
    tmp_out = []
    for fish_pic_id in range(1, 10000):
        # TODO: refactor to env
        try:
            fish_pic_dict = FishPic('data/dbs/fishr.db').get(fish_pic_id)
            tmp_out.append('{}, "{}"'.format(fish_pic_id, fish_pic_dict))
        except:
            break

    out_csv = '\n'.join(tmp_out)

    return out_csv, 200, {'Content-Type': 'text/csv'}
