# -*- coding:utf-8 -*-
import os
import threading
import time
import json
import git
import getopt
import sys
import Logger

log = None

def applyyaml(path, ip, service):
    if dircontainfile(path, service+".yaml") == False:
        f = open(os.path.join(path, "demo.yaml"), "r")
        str = f.read()
        f.close()

        str = str.replace("decisiontree", service)
        str = str.replace("127.0.0.1:5000", ip)

        f = open(os.path.join(path, service+".yaml"), "w+")
        f.write(str)
        f.close()

    cmd = "kubectl delete -f "+os.path.join(path, service+".yaml")+";\n"
    print("执行：" + cmd)
    os.system(cmd)

    time.sleep(10)

    cmd = "kubectl apply -f "+os.path.join(path, service+".yaml")
    print(u"执行：" + cmd)
    log.debug(u"执行：" + cmd)
    os.system(cmd)

oldcommit = ""

def checkgitpull(remote):
    global oldcommit

    try:
        commits = remote.pull()
    except BaseException as e:
        print(u"git pull失败")
        log.error(u"git pull失败")
        return False

    if len(commits) > 1:
        return True

    commit = str(commits[0].commit)

    repo.close()

    ret = (commit in oldcommit)
    oldcommit = commit

    return ret == False

def createimage(path, ip, service):
    image = ip+"/"+service
    cmd  = "cd "+os.path.join(path, service)+";\n"
    cmd += "docker build -t "+ image+" .;\n"
    cmd += "docker push "+image+";\n"
    cmd += "docker rmi "+image

    print(u"执行："+cmd)
    log.debug(u"执行："+cmd)

    os.system(cmd)

def listdir(path, list_name):
    dirs = []

    try:
        for file in os.listdir(path):
            file_path = os.path.join(path, file)

            if os.path.isdir(file_path):
                listdir(file_path, list_name)
            elif os.path.splitext(file_path)[1] != '.log':
                list_name.append(file_path)
    except BaseException as e:
        repr(e)

def  dircontainfile(path, filename):
    ret = False

    try:
        for file in os.listdir(path):
            file_path = os.path.join(path, file)

            if os.path.isdir(file_path):
                continue

            if filename in file:
                ret = True

                break
    except BaseException as e:
        repr(e)

    return ret

class MicroServiceManager(threading.Thread):
    def __init__(self, rootpath, repopath, remote, servicesfile, ip):
        threading.Thread.__init__(self)
        self.rootpath = rootpath #仓库所在目录
        self.repopath = repopath #仓库目录
        self.remote = remote #远程git仓库地址
        self.servicepath = os.path.join(repopath, "services")
        self.yamlpath = os.path.join(repopath, "yamls")
        self.ip = ip #docker 镜像仓库IP地址
        self.ServiceTimes = {}
        self.done = False
        self.servicesfile = servicesfile #服务更新时间记录文件
        self.commit = ""

    def init(self):
        try:
            #TODO 增加启动初始化ServiceTimes
            # f = open("/etc/microservicemanager/services.json")
            f = open(self.servicesfile, "r+")
            str = f.read()
            f.close()

            self.ServiceTimes = json.loads(str)
        except BaseException as e:
            repr(e)

        return

    #检查远程仓库更新
    def checkgitupdate(self):
        if os.path.exists(self.repopath) == False:
            os.system("git clone " + self.remote + " " + self.repopath)
            return True

        return False
        # return checkgitpull(self.repopath, self.commit)

    def saveservices(self):
        f = open(self.servicesfile, "w+")
        str = json.dumps(self.ServiceTimes)
        f.write(str)
        f.close()

        return

    def checkservicesupdate(self, service):
        file_path = os.path.join(self.servicepath, service)
        time = os.path.getmtime(file_path)

        if service in self.ServiceTimes:
            if time <= self.ServiceTimes[service]:
                return -1

        return time

    def getupdateservices(self):
        services = {}

        try:
            for file in os.listdir(self.servicepath):
                file_path = os.path.join(self.servicepath, file)

                if os.path.isdir(file_path) == False:
                    continue

                if dircontainfile(file_path, "dockerfile") == False and dircontainfile(file_path, "Dockerfile") == False:
                    continue

                time = self.checkservicesupdate(file)

                if time < 0:
                    continue

                print(u"微服务" + file + u"需要更新\n")
                log.warn(u"微服务" + file + u"需要更新\n")

                services[file] = time
        except BaseException as e:
            repr(e)

        return services

    def updateservice(self, service, time):
        try:
            createimage(self.servicepath, self.ip, service)
            applyyaml(self.yamlpath, self.ip, service)
            self.ServiceTimes[service] = time
        except BaseException as e:
            repr(e)

    def updateallservices(self):
        services = self.getupdateservices()

        if len(services) < 1:
            return False

        for service in services:
            self.updateservice(service, services[service])

        # TODO 保存记录ServiceTimes
        self.saveservices()

        return True

    def stop(self):
        self.done = True

    def run(self):
        lasttime = 0

        while self.done == False:
            now = time.time()

            if now < lasttime+10:
                time.sleep(0.5)
                continue

            lasttime = now
            #
            # if self.checkgitupdate() == False:
            #     continue
            self.updateallservices()

        print("微服务管理器退出\n")

# applyyaml("/opt/microservices/yamls/", "192.168.11.215", "api")
def readConfigs(file):
    config = {}

    try:
        f = open(file, "r+")
        lines = f.readlines()
    except BaseException as e:
        print(u"指定的配置文件"+file+"打开失败")
        log.error(u"指定的配置文件"+file+"打开失败")
        return config

    for l in lines:
        l = l.split("#")[0]

        if len(l) < 3:
            continue

        l = l.replace(" ", "")
        keyval = l.split("=")

        if len(keyval) != 2 or len(keyval[0]) < 1 or len(keyval[1]) < 1:
            continue

        # if int(keyval[1]) < 1:
        #     continue

        keyval[1] = keyval[1].replace("\n", "")
        config[keyval[0]] = keyval[1].replace("\r", "")

        # print "目录"+keyval[0]+"下的日志保存"+str(config[keyval[0]])+"天"

    f.close()

    if "reporoot" not in config:
        print(u"缺少版本库跟路径配置")
        log.error(u"缺少版本库跟路径配置")
        return None

    if "remoterepo" not in config:
        print(u"缺少远程版本库地址")
        log.error(u"缺少远程版本库地址")
        return None

    if "imageserver" not in config:
        print(u"缺少docker镜像服务器地址")
        log.error(u"缺少docker镜像服务器地址")
        return None

    return config

# reporoot = "/opt"
# repopath = os.path.join(reporoot, "micro_services")

def usage():
    print("-c,--configfile= 指定配置文件路径\n")

def createLocalRepo(repopath):
    try:
        print(u"创建本地仓库")
        log.debug(u"创建本地仓库")
        repo = git.Repo(repopath)
        print(u"创建远程仓库")
        log.debug(u"创建远程仓库")
        remote = repo.remote()

        return repo, remote
    except BaseException as e:
        repr(e)
        print(u"创建本地版本库失败")
        log.error(u"创建本地版本库失败")

        return None,None

if __name__ == '__main__':
    log = Logger.getLogger("serviceupdate", 3)

    try:
        options, args = getopt.getopt(sys.argv[1:], "hc:", ["help", "configfile="])
    except getopt.GetoptError:
        sys.exit()

    configfile = None

    for name, value in options:
        if name in ("-h", "--help"):
            usage()
        if name in ("-c", "--configfile"):
            print(u'配置文件为：', value)
            log.debug(u'配置文件为：'+value)
            configfile = value

    if configfile == None:
        print(u"必须指定一个配置文件")
        log.error(u"必须指定一个配置文件")
        exit(-1)

    configs = readConfigs(configfile)

    if configs == None:
        exit(-1)

    reporoot = configs["reporoot"]
    repopath = os.path.join(reporoot, "micro_services")
    remoterepo = configs["remoterepo"]
    imageserver = configs["imageserver"]

    servicerecords = os.path.join(repopath, "services")
    servicerecords = os.path.join(servicerecords, "services.json")

    repo,remote = createLocalRepo(repopath)

    print(u"创建服务管理对象")
    servicemanager = MicroServiceManager(reporoot, repopath, remoterepo, servicerecords, imageserver)

    print(u"初始化服务管理对象")
    servicemanager.init()
    lasttime = 0

    print(u"开始检查更新")
    log.debug(u"开始检查更新")

    while True:
        now = time.time()

        if now < lasttime+10:
            time.sleep(0.1)
            continue

        lasttime = now

        if servicemanager.checkgitupdate() == False:
            if checkgitpull(remote) == False:
                print(u"版本库无更新")
                log.debug(u"版本库无更新")
                continue
            print(u"远程版本库更新")
        else:
            print(u"本地库不存在，从远程克隆")
            log.warn(u"本地库不存在，从远程克隆")
            repo, remote = createLocalRepo(repopath)

        if servicemanager.updateallservices():
            # 提交services.json更新
            repo.index.add([servicerecords])
            repo.index.commit(u"update services record")
            remote.push()

        print(u"更新完成")
        log.debug(u"更新完成")

    # raw_input(u"按Enter键退出\n")
    #
    # servicemanager.stop()
    #
    # time.sleep(1)