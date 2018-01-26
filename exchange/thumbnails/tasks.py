import logging
import time
from celery.task import task

from django.db.models.signals import post_save
from django.conf import settings
from geonode.layers.models import Layer
from geonode.maps.models import Map
from geonode.geoserver.helpers import ogc_server_settings
from requests import session
from requests.adapters import HTTPAdapter, Retry
from .models import is_automatic
from .models import save_thumbnail

logger = logging.getLogger(__name__)

# setup requests client with max retries
http_client = session()
http_client.verify = True
retry = Retry(
    total=4,
    status=4,
    backoff_factor=0.9,
    status_forcelist=[502, 503, 504],
    method_whitelist=set([
        'HEAD',
        'TRACE',
        'GET',
        'PUT',
        'POST',
        'OPTIONS',
        'DELETE'
    ])
)
http_client.mount('http://', HTTPAdapter(max_retries=retry))
http_client.mount('https://', HTTPAdapter(max_retries=retry))


def make_thumb_request(instance, baseurl, params=None):
    # Avoid using urllib.urlencode here because it breaks the url.
    # commas and slashes in values get encoded and then cause trouble
    # with the WMS parser.
    if params:
        p = "&".join("%s=%s" % item for item in params.items())
    else:
        p = ''

    thumbnail_create_url = baseurl + p
    logger.debug(
        'Thumbnail: Requesting thumbnail for %s. ',
        thumbnail_create_url
    )
    if (instance.storeType == 'remoteStore'):
        resp = http_client.get(thumbnail_create_url)
    else:
        # Login using basic auth as geoserver admin
        user = settings.GEOSERVER_USER
        pword = settings.GEOSERVER_PASSWORD
        resp = http_client.get(
            thumbnail_create_url,
            auth=(user, pword)
        )
    if 200 <= resp.status_code <= 299:
        if 'ServiceException' not in resp.content:
            return resp.content
        else:
            logger.debug(
                'Thumbnail: Encountered unexpected status code: %d.  '
                'Aborting.',
                resp.status_code)
            logger.debug(resp)
    return None


# Get a thumbnail image generated from GeoServer
#
# This is based on the function in GeoNode but gets
# the image bytes instead.
#
# @return PNG bytes.
#
def get_gs_thumbnail(instance):
    if (instance.storeType == 'remoteStore'):
        if (instance.service.type == 'REST'):
            thumbnail_create_url = "%s/info/thumbnail" % (instance.ows_url)
            content = make_thumb_request(instance, thumbnail_create_url)
            if content:
                return content
            return None

    if instance.class_name == 'Map':
        local_layers = []
        for layer in instance.layers:
            if layer.local:
                local_layers.append(layer.name)
        layers = ",".join(local_layers).encode('utf-8')
        if(len(local_layers) == 0):
            return None
    else:
        layers = instance.typename.encode('utf-8')
        logger.debug('Instance storeType: %s', instance.storeType)

    params = {
        'layers': layers,
        'format': 'image/png8',
        'width': 200,
        'height': 150,
        'TIME': '-99999999999-01-01T00:00:00.0Z/99999999999-01-01T00:00:00.0Z',
        'crs': 'EPSG:3857'
    }

    baseurl = ogc_server_settings.LOCATION + \
        "wms/reflect?"

    if (instance.storeType == 'remoteStore'):
        params['request'] = 'GetMap'
        params['service'] = 'wms'
        params['version'] = '1.3.0'
        params['crs'] = 'EPSG:4326'
        params['bbox'] = '%s,%s,%s,%s' % (
            instance.bbox_y0,
            instance.bbox_x0,
            instance.bbox_y1,
            instance.bbox_x1
        )
        params['styles'] = ''

        baseurl = instance.ows_url + '?'
        del params['TIME']

    content = make_thumb_request(instance, baseurl, params)
    if content:
        return content

    # try using jpeg rather than png
    params['format'] = 'image/jpeg'
    content = make_thumb_request(instance, baseurl, params)
    if content:
        return content

    # try with CRS=84
    params['crs'] = 'CRS:84'
    params['bbox'] = '%s,%s,%s,%s' % (
        instance.bbox_x0,
        instance.bbox_y0,
        instance.bbox_x1,
        instance.bbox_y1
    )
    content = make_thumb_request(instance, baseurl, params)
    if content:
        return content

    return None


@task(
    max_retries=1,
)
def generate_thumbnail_task(instance_id, class_name):
    obj_type = None
    if class_name == 'Layer':
        try:
            instance = Layer.objects.get(typename=instance_id)
            obj_type = 'layers'
        except Layer.DoesNotExist:
            # Instance not saved yet, nothing more we can do
            logger.debug(
                'Thumbnail: Layer \'%s\' does not yet exist, cannot '
                'generate thumbnail. Trying one more time in 5 seconds.',
                instance_id)
            time.sleep(5)
            try:
                instance = Layer.objects.get(typename=instance_id)
                obj_type = 'layers'
            except Layer.DoesNotExist:
                # Instance not saved yet, nothing more we can do
                logger.debug(
                    'Thumbnail: Layer \'%s\' does not yet exist, cannot '
                    'generate thumbnail.',
                    instance_id)
                return

    elif class_name == 'Map':
        try:
            instance = Map.objects.get(id=instance_id)
            obj_type = 'maps'
        except Map.DoesNotExist:
            # Instance not saved yet, nothing more we can do
            logger.debug(
                'Thumbnail: Map \'%s\' does not yet exist, cannot '
                'generate thumbnail. Trying one more time in 5 seconds.',
                instance_id)
            time.sleep(5)
            try:
                instance = Map.objects.get(id=instance_id)
                obj_type = 'maps'
            except Map.DoesNotExist:
                # Instance not saved yet, nothing more we can do
                logger.debug(
                    'Thumbnail: Map \'%s\' does not yet exist, cannot '
                    'generate thumbnail.',
                    instance_id)
                return
    else:
        logger.debug(
            'Thumbnail: Unsupported class: %s. Aborting.', class_name)
        return

    logger.debug(
        'Thumbnail: Generating thumbnail for \'%s\' of type %s.',
        instance_id, class_name)
    if(instance_id is not None and is_automatic(obj_type, instance_id)):
        # have geoserver generate a preview png and return it.
        thumb_png = get_gs_thumbnail(instance)

        if(thumb_png is not None):
            logger.debug(
                'Thumbnail: Thumbnail successfully generated for \'%s\'.',
                instance_id)
            if (instance.is_remote):
                save_thumbnail(obj_type, instance.service_typename,
                               'image/png', thumb_png, True)
            else:
                save_thumbnail(obj_type, instance_id,
                               'image/png', thumb_png, True)
        else:
            logger.debug(
                'Thumbnail: Unable to get thumbnail image from '
                'GeoServer for \'%s\'.',
                instance_id)


# This is used as a post-save signal that will
# automatically geneirate a new thumbnail if none existed
# before it.
def generate_thumbnail(instance, sender, **kwargs):
    instance_id = None
    # flake8 issue F841
    # obj_type = None
    if instance.class_name == 'Layer':
        instance_id = instance.typename
        # flake8 issue F841
        # obj_type = 'layers'
    elif instance.class_name == 'Map':
        instance_id = instance.id
        # flake8 issue F841
        # obj_type = 'maps'

    if instance_id is not None:
        if instance.is_published:
            logger.debug(
                'Thumbnail: Issuing generate thumbnail task for \'%s\'.',
                instance_id)
            generate_thumbnail_task.delay(
                instance_id=instance_id, class_name=instance.class_name)
        else:
            logger.debug(
                'Thumbnail: Instance \'%s\' is not published, skipping '
                'generation.',
                instance_id)
    else:
        logger.debug(
            'Thumbnail: Unsupported class: \'%s\'. Unable to generate '
            'thumbnail.',
            instance.class_name)


def register_post_save_functions():
    # Disconnect first in case this function is called twice
    logger.debug('Thumbnail: Registering post_save functions.')
    post_save.disconnect(generate_thumbnail, sender=Layer)
    post_save.connect(generate_thumbnail, sender=Layer, weak=False)
    post_save.disconnect(generate_thumbnail, sender=Map)
    post_save.connect(generate_thumbnail, sender=Map, weak=False)


register_post_save_functions()
