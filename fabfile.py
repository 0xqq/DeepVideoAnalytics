import os,logging
from fabric.api import task,local,run,put,get,lcd,cd,sudo
import django,sys
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M',
                    filename='logs/fab.log',
                    filemode='a')



@task
def shell():
    local('python manage.py shell')



@task
def local_static():
    local('python manage.py collectstatic')


@task
def migrate():
    local('python manage.py makemigrations')
    local('python manage.py migrate')


@task
def worker(queue_name,conc=1):
    conc = int(conc)
    command = 'celery -A dca worker -l info -c {} -Q {} -n {}.%h -f logs/celery.log'.format(conc,queue_name,queue_name)
    if sys.platform != 'darwin':
        command = "source ~/.profile && "+command
    local(command=command)


@task
def server():
    local("python manage.py runserver")

@task
def start_server_container(test=False):
    local('sleep 60')
    migrate()
    local('python start_extractor.py &')
    local('python start_indexer.py &')
    local('python start_detector.py &')
    if test:
        ci()
    local('python manage.py runserver 0.0.0.0:8000')


@task
def clean():
    local('python manage.py flush --no-input')
    migrate()
    local("rm logs/*.log")
    local("rm -rf ~/media/*")
    local("mkdir ~/media/queries")


@task
def ci():
    with lcd("tests"):
        local('wget https://www.dropbox.com/s/xtpkb18i6hn39ht/Goldeneye.mp4')
        local('wget https://www.dropbox.com/s/cjo9b68poqk7gy2/TomorrowNeverDies.mp4')
        local('wget https://www.dropbox.com/s/xwbk5g1qit5s9em/WorldIsNotEnough.mp4')
        local('wget https://www.dropbox.com/s/misaejsbz6722pd/test.png')
     local('python run_test.py')
