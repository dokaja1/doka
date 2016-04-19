#!/usr/bin/env python
import subprocess
from subprocess import Popen, PIPE, STDOUT
import sys, paramiko
import time
import os
import re
import logging

#paramiko.common.logging.basicConfig(level=paramiko.common.DEBUG)

computeTozone = None
computeTotest = False
customer = None
customerUUID = None
neededNetUUIDfound = None
ChassisCheck = False
instanceUUID = None
ifSRIOV = False
iLoHOSTNAME = None
addComputeProcess = False
iLoIP = None
ifDisabledSSHtimeout = False
ForChassisCheck = None
rocksIP = None


class Log():
    def success(self, message):
        print(color.GREEN + message + color.END)
    def fail(self, message):
        print(color.RED + message + color.END)  
    def successFinal(self, message):
        print(color.GREEN + color.UNDERLINE + message + color.END)
    def greetings(self, message):
        print(color.BLUE + message + color.END)

log = Log()   

def check_output(command):
    global ForChassisCheck
    try:
        respone=subprocess.check_output(command, shell=True)
        return True
    except subprocess.CalledProcessError as e:
        return False
        
class color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

def check_precondisions():
    global customer
    global neededNetUUIDfound
    global FourChassisCheck
    global labelLinefound
    global ifDisabledSSHtimeout
    global ForChassisCheck
    global ChassisCheck
    global iLoIP
    global computeTotest
    global iLoHOSTNAME
    
    #remove autoRemoveAddCompute folder
    subprocess.call("rm -fr /export/ci/tools/autoRemoveAddCompute", shell=True)
    
    #script folder
    subprocess.call("mkdir -p /export/ci/tools/autoRemoveAddCompute", shell=True)
    
    #logger setting
    logging.basicConfig(filename='/export/ci/tools/autoRemoveAddCompute/add_compute_auto.log',level=logging.DEBUG)
    logging.basicConfig(format='%(asctime)s %(message)s')
    
    #checking and setting ssh timeout to disable
    proc = subprocess.Popen("cat /etc/puppet/hiera/security.yaml |grep -w 'security_sshd: true'", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    ifDisabledSSHtimeout = not not stdout
    logging.info(stdout)
    logging.info(stderr)
    #print "stdout",stdout
    #print "stderr",stderr
    
    if ifDisabledSSHtimeout:
        log.fail("ssh timeout not disabled. disabling \n")
        logging.info ("ssh timeout not disabled. disabling")
        subprocess.call("sed -i 's/true/false/g' /etc/puppet/hiera/security.yaml", shell=True)
        log.fail("restarting sshd service \n")
        logging.info ("restarting sshd service")
        subprocess.call("/bin/systemctl restart  sshd.service", shell=True)
        log.fail("please restart ssh session. verify that session won't timed-out again and try again \n")
        logging.info ("please restart ssh session. verify that session won't timed-out again and try again")
        
        sys.exit()
    
    
    #kill already running add_compute process
    subprocess.call("ps aux |grep -w '/opt/rocks/sbin/insert-ethers-cli --hostname=compute' |grep -v 'grep' > /export/ci/tools/autoRemoveAddCompute/add_compute_process.txt", stderr=open(os.devnull, 'wb'), shell=True)
    addComputeProcess=subprocess.check_output("sed -n '$p' /export/ci/tools/autoRemoveAddCompute/add_compute_process.txt > /export/ci/tools/autoRemoveAddCompute/add_compute_process_extracted.txt ", shell=True).strip()
    addComputeProcess=subprocess.check_output("cut -c 5-15  /export/ci/tools/autoRemoveAddCompute/add_compute_process_extracted.txt", shell=True).strip()
    if addComputeProcess:
        log.fail("killing {0} an already running add_compute process \n".format(addComputeProcess))
        subprocess.call("kill {0}".format(addComputeProcess), shell=True)
        logging.info("the add_compute process killed is {0}".format(addComputeProcess))
    
    

   
    #check if 4 chasis
    #yes = set(['yes','y', 'ye', ''])
    #no = set(['no','n'])

    #FourChassisCheck = raw_input("Is it 4 chassis setup ? (Y/n) \n").lower()
    #if FourChassisCheck in yes:
    #    FourChassisCheck=True
        #print "FourChassisCheck is {0}".format(FourChassisCheck)
    #elif FourChassisCheck in no:
    #    FourChassisCheck=False
        #print "FourChassisCheck is {0}".format(FourChassisCheck)
    #else:
    #    log.fail("Please respond with 'yes' or 'no' \n")
    #    sys.exit()
       
       
    #setup check       
    subprocess.call("dmidecode |grep 'Product Name' > /export/ci/tools/autoRemoveAddCompute/product.txt", shell=True)
    ForChassisCheck=subprocess.check_output("cut -c 32-38 < /export/ci/tools/autoRemoveAddCompute/product.txt", shell=True).strip()
    if ForChassisCheck == 'Gen9':
        ChassisCheck = True
        print ""
        log.success("The setup is {0}. Proceeding \n".format(ForChassisCheck))
    else:
        ChassisCheck = False
        print ""
        log.success("The setup is {0}. Proceeding \n".format(ForChassisCheck))
    
    
        
def getArguments():
    global rocksIP
    global computeTotest
    global computeTozone
    global customer
    global iLoIP
    global iLoHOSTNAME
    
    if len(sys.argv)>=4:
        #rocksIP=sys.argv[1]
        customer=sys.argv[1]
        computeTotest=sys.argv[2]
        computeTozone=sys.argv[3]
        logging.info ("got input from web")
        
        print ("THE customer is: {0} computeTotest is: {1} computeTozone is: {2}".format(customer,computeTotest,computeTozone))
        logging.info("THE customer is: {0} computeTotest is: {1} computeTozone is: {2}".format(customer,computeTotest,computeTozone))
        
        #cut compute iLo ip and Hostname
        subprocess.call("cat /var/cluster/ipmi |grep -w {0} > /export/ci/tools/autoRemoveAddCompute/compute_iLO_ip.txt".format(computeTotest), shell=True)
        iLoIP = subprocess.check_output("cut -d':' -f2 /export/ci/tools/autoRemoveAddCompute/compute_iLO_ip.txt", shell=True).strip()
        iLoHOSTNAME = subprocess.check_output("cut -d':' -f1 /export/ci/tools/autoRemoveAddCompute/compute_iLO_ip.txt", shell=True).strip()
        print "compute hostname is {0}".format(iLoHOSTNAME)
        logging.info("compute hostname is {0}".format(iLoHOSTNAME))
        print "compute iLo ip is {0}".format(iLoIP)
        logging.info("compute iLo ip is {0}".format(iLoIP))
        print ""
    
        #sys.exit()
        
    else:
        
        getParameters()
        logging.info ("calling get parameters")
            

def getParameters():
    global computeTotest
    global computeTozone
    global iLoHOSTNAME
    global iLoIP
    global ifSRIOV
    global neededNetUUIDfound
        
    #input customer
    log.greetings("Please run Join & Create Configuration via LoveManager")
    print ""
    customer = raw_input("Enter the tenant name after it finished. e.g CUSTOMER_1 \n")
    logging.info("customer is {0}".format(customer))
    #print " customer is {0}".format(customer)
    
    #check if configured
    if customer is not None:
        subprocess.call("source /root/keystonerc_admin; keystone tenant-list |grep -w {0} > /export/ci/tools/autoRemoveAddCompute/customer.txt".format(customer), shell=True)
       
       
       #check if column labels line is in customer.txt
        def checkLabelsExist():
           global datafile
           global labelLinefound
           global neededNetUUIDfound
           
           datafile = file('/export/ci/tools/autoRemoveAddCompute/customer.txt')
           labelLinefound = False
           for line in datafile:
               if 'id' in line:
                   print("labels found")
                   labelLinefound = True
               break

        checkLabelsExist()
    
        if labelLinefound:
            subprocess.call("sed -n '1!p' /export/ci/tools/autoRemoveAddCompute/customer.txt > /export/ci/tools/autoRemoveAddCompute/customer_extracted.txt", shell=True)
            customerUUID=subprocess.check_output("cut -c 3-34 < /export/ci/tools/autoRemoveAddCompute/customer_extracted.txt", shell=True).strip()
        #label line not found
        else:
            customerUUID=subprocess.check_output("cut -c 3-34 < /export/ci/tools/autoRemoveAddCompute/customer.txt", shell=True).strip()
        #print "customerUUID is {0}".format(customerUUID)
        if not customerUUID:
            log.fail("Customer Not Found. Check input or LoveManager")
            logging.info("Customer Not Found. Check input or LoveManager")
            sys.exit()
        else:
            subprocess.call("source /root/keystonerc_admin; neutron net-list |grep PUBLIC > /export/ci/tools/autoRemoveAddCompute/nets_public.txt".format(customerUUID), shell=True)
            subprocess.call("cut -c 3-38 /export/ci/tools/autoRemoveAddCompute/nets_public.txt > /export/ci/tools/autoRemoveAddCompute/nets_public_extracted.txt", shell=True)
            uuid_found = False
            with open('/export/ci/tools/autoRemoveAddCompute/nets_public_extracted.txt') as f:
                  for line in f:
                     network_uuid=line.strip()
                     try:
                         #print "customerUUID is {0}".format(customerUUID)
                         #print "network_uuid is {0}".format(network_uuid)
                         neededNetUUIDfound=subprocess.check_output("source /root/keystonerc_admin; neutron net-show {0} |grep {1} ".format(network_uuid,customerUUID), shell=True).strip()
                         neededNetUUIDfound=network_uuid
                         print ("neededNetUUIDfound is {0}").format(neededNetUUIDfound) 
                         logging.info("neededNetUUIDfound is {0}".format(neededNetUUIDfound))
                         print ""
                         log.success("Customer Found & PUBLIC Network UUID Found. Continuing")
                         logging.info("Customer Found & PUBLIC Network UUID Found. Continuing")
                         uuid_found = True
                     except subprocess.CalledProcessError as e:
                         pass

            if not uuid_found:
                print""
                log.fail("PUBLIC Network Not Found. Check TENANT input") 
                logging.info("PUBLIC Network Not Found. Check TENANT input")        
                sys.exit()
            
    else:
        sys.exit()
     
    print ""     
    computeTotest = raw_input("Enter compute to test. e.g: compute-0-10 \n").strip()
    logging.info("computeTotest is {0}".format(computeTotest))
    if not check_output ("source /root/keystonerc_admin; nova availability-zone-list |grep -w {0}".format(computeTotest)):
        log.fail("The compute is not found. Check input")
        logging.info("The compute is not found. Check input")
        sys.exit()
    else:
        print""
        log.success("Compute found. Continuing \n") 
        logging.info("Compute found. Continuing \n")
    
    computeTozone = raw_input("Enter which zone to move compute to. e.g: zone1 , ENTER for default choice (zone0) \n") 
    logging.info("computeTozone is {0}".format(computeTozone))
    if computeTozone == "":
       computeTozone = 'zone0'
    else:
        if not check_output ("source /root/keystonerc_admin; nova aggregate-list |grep -w {0}".format(computeTozone)):
            log.fail("The zone is not found. Check input")
            logging.info("The zone is not found. Check input")
            sys.exit()
        else:
            log.success("Zone found. Continuing \n") 
            logging.info("Zone found. Continuing \n")
            

    #cut compute iLo ip and Hostname
    subprocess.call("cat /var/cluster/ipmi |grep -w {0} > /export/ci/tools/autoRemoveAddCompute/compute_iLO_ip.txt".format(computeTotest), shell=True)
    iLoIP = subprocess.check_output("cut -d':' -f2 /export/ci/tools/autoRemoveAddCompute/compute_iLO_ip.txt", shell=True).strip()
    iLoHOSTNAME = subprocess.check_output("cut -d':' -f1 /export/ci/tools/autoRemoveAddCompute/compute_iLO_ip.txt", shell=True).strip()
    print "compute hostname is {0}".format(iLoHOSTNAME)
    logging.info("compute hostname is {0}".format(iLoHOSTNAME))
    print "compute iLo ip is {0}".format(iLoIP)
    logging.info("compute iLo ip is {0}".format(iLoIP))
    print ""
        
    #check
    #print " customer is: {0} computeTotest is: {1} computeTozone is: {2}".format(customer,computeTotest,computeTozone)
    #sys.exit()
    
def check_SRIOV_zone():
    global computeTotest
    global computeTozone
    global ifSRIOV

    #check sriov zone
    p = subprocess.Popen("cat /export/apps/openstack/openstack.cfg |grep sriov_zones > /export/ci/tools/autoRemoveAddCompute/sriovZone.txt".format(computeTotest), stdout=PIPE, stdin=PIPE, stderr=PIPE, shell=True)
    ifSRIOV=check_output("cat /export/ci/tools/autoRemoveAddCompute/sriovZone.txt |grep {0}".format(computeTozone))
    if ifSRIOV:
        log.success("The zone is SRIOV \n")
        logging.info("The zone is SRIOV ")
    else:
        log.success("The zone is OVS \n")
        logging.info("The zone is OVS ")
    
    stdout, stderr = p.communicate()    
    print "stdout:", stdout
    print "stderr:", stderr


def check_ifSRIOV(): 
    global ifSRIOV
    global iLoHOSTNAME
    global ForChassisCheck
        
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print "Connecting to {0} \n".format(iLoHOSTNAME)
    client.connect(iLoHOSTNAME, username='root', password='Mc10vin!!', look_for_keys=False)
        
    for i in range(1):
        stdin, stdout, stderr = client.exec_command("cat /etc/nova/nova.conf |grep -w pci_passthrough_whitelist={")
        response=stdout.read().strip()
        print response
        if response:
            ifSRIOV = True
            print""
            log.success("The compute is SRIOV")
            logging.info("The compute is SRIOV")
            print ""
            log.successFinal("Going to remove compute. WAIT!!! It would take time for ceph to recover before script can continue")
            logging.info("Going to remove compute. WAIT!!! It would take time for ceph to recover before script can continue")
            time.sleep(5)            
        else:       
            print""
            log.success("The compute is not SRIOV") 
            logging.info("The compute is not SRIOV")
            print ""
            log.success("Going to remove compute. WAIT!!! It would take time for ceph to recover before script can continue")
            logging.info("Going to remove compute. WAIT!!! It would take time for ceph to recover before script can continue")
            time.sleep(5)

    client.close()

def remove_compute():
    global computeTozone
    global computeTotest
    global iLoHOSTNAME
    global iLoIP
    global ForChassisCheck
    global ifSRIOV
 

    #remove compute
    if ifSRIOV:
        p = subprocess.Popen("source /root/keystonerc_admin; python /export/ci/tools/remove_compute.py {0} --compute_type sriov".format(computeTotest), stdout=PIPE, stdin=PIPE, stderr=PIPE, shell=True)
        time.sleep(1)
        stdout = p.communicate(input=b'y\n')[0]
        time.sleep(5)
        print "removing compute {0}".format(computeTotest)
        logging.info("removing compute {0}".format(computeTotest))
 
        print "stdout:", stdout
        p.wait()
    else:
        p = subprocess.Popen("source /root/keystonerc_admin; python /export/ci/tools/remove_compute.py {0} --compute_type ovs".format(computeTotest), stdout=PIPE, stdin=PIPE, stderr=PIPE, shell=True)
        time.sleep(1)
        stdout = p.communicate(input=b'y\n')[0]
        time.sleep(5)
        print "removing compute {0}".format(computeTotest)
        logging.info("removing compute {0}".format(computeTotest))
 
        print "stdout:", stdout
        p.wait()
       
    
    #POWER OFF HARD
    log.success("going to POWER OFF HARD compute. Wait 1 minute \n")
    time.sleep(60)
    proc = subprocess.Popen("ipmitool -H {0} -I lanplus -U hp -P password chassis power off hard".format(iLoIP), stdout=PIPE, stdin=PIPE, stderr=PIPE, shell=True)
     
    #check compute is off
    #powerCheck = False
    #while not powerCheck:
    #    print "making sure the compute is off"
    #    print ("powerCheck is: {0}".format(powerCheck))
    #    time.sleep(10)
    #    p = subprocess.Popen("ipmitool -H {0} -I lanplus -U hp -P password chassis power status".format(iLoIP), stdout=PIPE, stdin=PIPE, stderr=PIPE, shell=True)
    #    output = p.communicate()[0]
        #for line in p.stdout:
        #    sys.stdout.write(line)
        #    output.append(line)
        #p.wait()
    #    print output
        
    #    if 'Chassis Power is off' in "".join(output):
    #        powerCheck = True
    #        print ("powerCheck is: {0}".format(powerCheck))
            
    proc.communicate()
    
    add_compute(iLoIP) 
    
    #print "got here 01"
    return iLoIP
    

def add_compute(iLoIP): 
    global ForChassisCheck
    global ifSRIOV

    #add compute
    if computeTozone is not None and not ifSRIOV:
       print "Calling add_compute.py 1 \n"
       p = subprocess.Popen("source /root/keystonerc_admin; python /export/ci/tools/add_compute.py {1} --zone {0} --compute_type ovs --ilo_ip {2} --ilo_username hp --ilo_password password".format(computeTozone,computeTotest,iLoIP), stdin=PIPE, stderr=PIPE, shell=True)
       time.sleep(20)
       log.success("adding compute {0} to {1}".format(computeTotest,computeTozone))
       logging.info("adding compute {0} to {1}".format(computeTotest,computeTozone))

    elif computeTozone == "" and not ifSRIOV :
       print "Calling add_compute.py 2 \n"
       p = subprocess.Popen("source /root/keystonerc_admin; python /export/ci/tools/add_compute.py {1} --compute_type ovs --ilo_ip {2} --ilo_username hp --ilo_password password".format(computeTotest,iLoIP), stdin=PIPE, stderr=PIPE, shell=True)
       time.sleep(20)
       log.success("adding compute {0} to default zone0".format(computeTotest))
       logging.info("adding compute {0} to default zone0".format(computeTotest))
       
    elif computeTozone is not None and ifSRIOV :
       print "Calling add_compute.py 3 \n"
       p = subprocess.Popen("source /root/keystonerc_admin; python /export/ci/tools/add_compute.py {1} --zone {0} --compute_type sriov --ilo_ip {2} --ilo_username hp --ilo_password password".format(computeTozone,computeTotest,iLoIP), stdin=PIPE, stderr=PIPE, shell=True)
       time.sleep(20)
       log.success("adding compute {0} to default zone0".format(computeTotest))
       logging.info("adding compute {0} to default zone0".format(computeTotest))
       
    elif computeTozone == "" and ifSRIOV :
       print "Calling add_compute.py 4 \n"
       p = subprocess.Popen("source /root/keystonerc_admin; python /export/ci/tools/add_compute.py {1} --compute_type sriov --ilo_ip {2} --ilo_username hp --ilo_password password".format(computeTotest,iLoIP), stdin=PIPE, stderr=PIPE, shell=True)
       time.sleep(20)
       log.success("adding compute {0} to default zone0".format(computeTotest))
       logging.info("adding compute {0} to default zone0".format(computeTotest))
    
    stdout, stderr = p.communicate()
    print "stdout:", stdout
    print "stderr:", stderr
 

#change bootorder for compute and power on    
password = "password"
command3 = "POWER ON"
command1 = "cd system1/bootconfig1"
command2 = "set bootsource5 bootorder=1;"
command4 = "set bootsource4 bootorder=1;"
command5 = "power off hard"
username = "hp"
port = 22

def connect():
    global password, command, username, port, ChassisCheck, ForChassisCheck, iLoIP
    if ChassisCheck:
         
         #print "FourChassisCheck is {0}".format(FourChassisCheck)
         client = paramiko.SSHClient()
         client.load_system_host_keys()
         client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

         client.connect(iLoIP, port=port, username=username, password=password, look_for_keys=False, allow_agent=False)
           
         #cd system1/bootconfig1
         stdin, stdout, stderr = client.exec_command(command1)
         print stdout.readlines()
         cmdOutput=stdout.readlines()
         cmdError=stderr.readlines()
         
         if cmdOutput:
             if "status_tag=COMMAND COMPLETED" in cmdOutput:
                 log.success("COMMAND [cd system1/bootconfig1] COMPLETED")
             elif "status_tag=COMMAND PROCESSING FAILED" in cmdOutput:
                 log.fail("COMMAND PROCESSING FAILED")
                 sys.exit()
         time.sleep(10)
         
         #set bootsource4 bootorder=1
         stdin, stdout, stderr = client.exec_command(command4)
         print stdout.readlines()
         cmdOutput=stdout.readlines()
         cmdError=stderr.readlines()       
         
         if cmdOutput:
             if "status_tag=COMMAND COMPLETED" in cmdOutput:
                 log.success("COMMAND [set bootsource4 bootorder=1] COMPLETED")
             elif "status_tag=COMMAND PROCESSING FAILED" in cmdOutput:
                 log.fail("COMMAND PROCESSING FAILED")
                 sys.exit()
         time.sleep(10)
         
         #POWER ON
         #stdin, stdout, stderr = client.exec_command(command3)
         #print stdout.readlines()
         #cmdOutput=stdout.readlines()
         #cmdError=stderr.readlines()
         
         #if cmdOutput:
         #    if "status_tag=COMMAND COMPLETED" in cmdOutput:
         #        log.success("COMMAND [POWER ON] COMPLETED")
         #    elif "status_tag=COMMAND PROCESSING FAILED" in cmdOutput:
         #        log.fail("COMMAND PROCESSING FAILED. Check if iLo was already POWER ON")
         #        sys.exit()

    
    elif not ChassisCheck:

         #print "FourChassisCheck is {0}".format(FourChassisCheck)
         client = paramiko.SSHClient()
         client.load_system_host_keys()
         client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

         client.connect(iLoIP, port=port, username=username, password=password, look_for_keys=False, allow_agent=False)
           
         #cd system1/bootconfig1
         stdin, stdout, stderr = client.exec_command(command1)
         print stdout.readlines()
         cmdOutput=stdout.readlines()
         cmdError=stderr.readlines()
         
         if cmdOutput:
             if "status_tag=COMMAND COMPLETED" in cmdOutput:
                 log.success("COMMAND [cd system1/bootconfig1] COMPLETED")
             elif "status_tag=COMMAND PROCESSING FAILED" in cmdOutput:
                 log.fail("COMMAND PROCESSING FAILED")
                 sys.exit()
         time.sleep(10)
         
         #set bootsource5 bootorder=1
         stdin, stdout, stderr = client.exec_command(command2)
         print stdout.readlines()
         cmdOutput=stdout.readlines()
         cmdError=stderr.readlines()
         
         if cmdOutput:
             if "status_tag=COMMAND COMPLETED" in cmdOutput:
                 log.success("COMMAND [set bootsource5 bootorder=1] COMPLETED")
             elif "status_tag=COMMAND PROCESSING FAILED" in cmdOutput:
                 log.fail("COMMAND PROCESSING FAILED")
                 sys.exit()
         time.sleep(10)
         
 
         #POWER ON
         #stdin, stdout, stderr = client.exec_command(command3)
         #print stdout.readlines()
         #cmdOutput=stdout.readlines()
         #cmdError=stderr.readlines()
         
         #if cmdOutput:
         #    if "status_tag=COMMAND COMPLETED" in cmdOutput:
         #        log.success("COMMAND [POWER ON] COMPLETED")
         #    elif "status_tag=COMMAND PROCESSING FAILED" in cmdOutput:
         #        log.fail("COMMAND PROCESSING FAILED. Check if iLo was already POWER ON")
         #        sys.exit()
         
         
         client.close()

        
def check_instance():
    global instanceUUID
    global instanceIP
    global ifSRIOV
    global neededNetUUIDfound
    global ForChassisCheck
    
    print ("got neededNetUUIDfound going to lunch instance {0}").format(neededNetUUIDfound) 
    logging.info("got neededNetUUIDfound going to lunch instance {0}".format(neededNetUUIDfound))
    
    #lunch instance based on zone and SRIOV
    if computeTozone is not None and not ifSRIOV:
        print("computeTozone is not None and not ifSRIOV")
        print "SENDING:  source /root/keystonerc_admin; nova boot --image redhat7-v2 --flavor MEDIUM_2 --nic net-id={0} --security-groups CloudBand-SecurityGroup --availability-zone {1}:{2}.local on_{2}_{1}".format(neededNetUUIDfound,computeTozone,computeTotest)
        logging.info("SENDING:  source /root/keystonerc_admin; nova boot --image redhat7-v2 --flavor MEDIUM_2 --nic net-id={0} --security-groups CloudBand-SecurityGroup --availability-zone {1}:{2}.local on_{2}_{1}".format(neededNetUUIDfound,computeTozone,computeTotest))
        subprocess.call("source /root/keystonerc_admin; nova boot --image redhat7-v2 --flavor MEDIUM_2 --nic net-id={0} --security-groups CloudBand-SecurityGroup --availability-zone {1}:{2}.local on_{2}_{1}".format(neededNetUUIDfound,computeTozone,computeTotest), shell=True)
    elif ifSRIOV and computeTozone is not None:
        print("ifSRIOV and computeTozone is not None")
        p = subprocess.Popen("source /root/keystonerc_admin; neutron port-create {0} --binding:vnic-type direct".format(neededNetUUIDfound), stdout=PIPE, stdin=PIPE, stderr=PIPE, shell=True)
        stdout,stderr=p.communicate()
        FoundPortID=re.search("\| id\s+\| ([a-z0-9\-]+)\s+\|", stdout)
        if FoundPortID and len(FoundPortID.groups()):
            PortID=FoundPortID.groups()[0]
            print "Port ID is {0} \n".format(PortID)
        print "SENDING: source /root/keystonerc_admin; nova boot --image redhat6-5-v20 --flavor MEDIUM_2 --nic port-id={2} --security-groups CloudBand-SecurityGroup --availability-zone {0}:{1}.local on_{1}_{0}".format(computeTozone,computeTotest,PortID)
        logging.info("SENDING: source /root/keystonerc_admin; nova boot --image redhat6-5-v20 --flavor MEDIUM_2 --nic port-id={2} --security-groups CloudBand-SecurityGroup --availability-zone {0}:{1}.local on_{1}_{0}".format(computeTozone,computeTotest,PortID))
        subprocess.call("source /root/keystonerc_admin; nova boot --image redhat6-5-v20 --flavor MEDIUM_2 --nic port-id={2} --security-groups CloudBand-SecurityGroup --availability-zone {0}:{1}.local on_{1}_{0}".format(computeTozone,computeTotest,PortID), shell=True)
    elif ifSRIOV and computeTozone == "":
        print("ifSRIOV and computeTozone == """)
        p = subprocess.Popen("source /root/keystonerc_admin; neutron port-create {0} --binding:vnic-type direct".format(neededNetUUIDfound), stdout=PIPE, stdin=PIPE, stderr=PIPE, shell=True)
        stdout,stderr=p.communicate()
        FoundPortID=re.search("\| id\s+\| ([a-z0-9\-]+)\s+\|", stdout)
        if FoundPortID and len(FoundPortID.groups()):
            PortID=FoundPortID.groups()[0]
            print "Port ID is {0} \n".format(PortID)
        print "SENDING: source /root/keystonerc_admin; nova boot --image redhat6-5-v20 --flavor MEDIUM_2 --nic port-id={1} --security-groups CloudBand-SecurityGroup --availability-zone zone0:{0}.local on_{0}_zone0".format(computeTotest,PortID)
        logging.info("SENDING: source /root/keystonerc_admin; nova boot --image redhat6-5-v20 --flavor MEDIUM_2 --nic port-id={1} --security-groups CloudBand-SecurityGroup --availability-zone zone0:{0}.local on_{0}_zone0".format(computeTotest,PortID))
        subprocess.call("source /root/keystonerc_admin; nova boot --image redhat6-5-v20 --flavor MEDIUM_2 --nic port-id={1} --security-groups CloudBand-SecurityGroup --availability-zone zone0:{0}.local on_{0}_zone0".format(computeTotest,PortID), shell=True)
    else:
        print("got here 3")
        print "SENDING: source /root/keystonerc_admin; nova boot --image redhat7-v2 --flavor MEDIUM_2 --nic net-id={0} --security-groups CloudBand-SecurityGroup --availability-zone zone0:{1}.local on_{1}_zone0".format(neededNetUUIDfound,computeTotest)
        logging.info("SENDING: source /root/keystonerc_admin; nova boot --image redhat7-v2 --flavor MEDIUM_2 --nic net-id={0} --security-groups CloudBand-SecurityGroup --availability-zone zone0:{1}.local on_{1}_zone0".format(neededNetUUIDfound,computeTotest))
        subprocess.call("source /root/keystonerc_admin; nova boot --image redhat7-v2 --flavor MEDIUM_2 --nic net-id={0} --security-groups CloudBand-SecurityGroup --availability-zone zone0:{1}.local on_{1}_zone0".format(neededNetUUIDfound,computeTotest), shell=True)

    
    print "lunching instance going to sleep 1 minute... \n"
    time.sleep(60)
    
    
    #check instance if ACTIVE
    if computeTozone is not None:
        #print("got here 4")
        ifActive = False
        subprocess.call("source /root/keystonerc_admin; nova list --all-tenant |grep on_{1}_{0} > /export/ci/tools/autoRemoveAddCompute/instanceUUID.txt".format(computeTozone,computeTotest), shell=True)
        instanceUUID=subprocess.check_output("cut -c 3-38 < /export/ci/tools/autoRemoveAddCompute/instanceUUID.txt", shell=True).strip()
        if not check_output ("source /root/keystonerc_admin; nova show {0} |grep ACTIVE".format(instanceUUID)):
            log.fail("The instance on {1}_{0} is not running. Check why".format(computeTozone,computeTotest))
            logging.info("The instance on {1}_{0} is not running. Check why".format(computeTozone,computeTotest))
            sys.exit()                 
        else:
            log.success("The instance is ACTIVE. Continuing")
            logging.info("The instance is ACTIVE. Continuing")
                  
    elif computeTozone == "":         
        ifActive = False
        subprocess.call("source /root/keystonerc_admin; nova list --all-tenant |grep on_{0}_zone0 > /export/ci/tools/autoRemoveAddCompute/instanceUUID.txt".format(computeTotest), shell=True)
        instanceUUID=subprocess.check_output("cut -c 3-38 < /export/ci/tools/autoRemoveAddCompute/instanceUUID.txt", shell=True).strip()
        if not check_output ("source /root/keystonerc_admin; nova show {0} |grep ACTIVE".format(instanceUUID)): 
            log.fail("The instance on_{1}_zone0 is not running. Check why".format(computeTotest))
            logging.info("The instance on_{1}_zone0 is not running. Check why".format(computeTotest))
            sys.exit()              
        else:
            log.success("The instance is ACTIVE. Continuing")
            logging.info("The instance is ACTIVE. Continuing")
                
            
    
    #check instance has IP
    if computeTozone is not None:
        #print("got here 5")
        instanceIP = False
        #subprocess.call("source /root/keystonerc_admin; nova list --all-tenant |grep on{1}_zone{0} > /export/ci/tools/autoRemoveAddCompute/instanceUUID.txt".format(computeTozone,computeTotest), shell=True)
        #instanceUUID=subprocess.check_output("cut -c 3-38 < /export/ci/tools/autoRemoveAddCompute/instanceUUID.txt", shell=True).strip()
        subprocess.call("source /root/keystonerc_admin; nova show {0} |grep PUBLIC > /export/ci/tools/autoRemoveAddCompute/instanceIP.txt".format(instanceUUID), shell=True)
        instanceIP=subprocess.check_output("cut -c 42-60 < /export/ci/tools/autoRemoveAddCompute/instanceIP.txt", shell=True).strip()
        if instanceIP:
            log.success("The instance on_{1}_{0} Has IP {2}".format(computeTozone,computeTotest,instanceIP))
            logging.info("The instance on_{1}_{0} Has IP {2}".format(computeTozone,computeTotest,instanceIP))
        else:
            log.fail("The instance on_{1}_{0} Has no IP. Check why".format(computeTozone,computeTotest))
            logging.info("The instance on_{1}_{0} Has no IP. Check why".format(computeTozone,computeTotest))
            sys.exit()
    

    if computeTozone == "": 
        #print("got here 6") 
        instanceIP = False
        #subprocess.call("source /root/keystonerc_admin; nova list --all-tenant |grep on_{0} > /export/ci/tools/autoRemoveAddCompute/instanceUUID.txt".format(computeTotest), shell=True)
        #instanceUUID=subprocess.check_output("cut -c 3-38 < /export/ci/tools/autoRemoveAddCompute/instanceUUID.txt", shell=True).strip()
        subprocess.call("source /root/keystonerc_admin; nova show {0} |grep PUBLIC > /export/ci/tools/autoRemoveAddCompute/instanceIP.txt".format(instanceUUID), shell=True)
        instanceIP=subprocess.check_output("cut -c 42-60 < /export/ci/tools/autoRemoveAddCompute/instanceIP.txt", shell=True).strip()
        if instanceIP:
            log.success("The instance on_{0}_zone0 Has IP {1}".format(computeTotest,instanceIP))
            logging.info("The instance on_{0}_zone0 Has IP {1}".format(computeTotest,instanceIP))
        else:
            log.fail("The instance on_{0}_zone0 is not running. Check why".format(computeTotest))
            logging.info("The instance on_{0}_zone0 is not running. Check why".format(computeTotest))
            sys.exit()
        

    #check ping to instance
    ifPing = False
    subprocess.call("fping {0} -t 5000 > /export/ci/tools/autoRemoveAddCompute/pingResult.txt".format(instanceIP), shell=True)
    if not check_output ("cat /export/ci/tools/autoRemoveAddCompute/pingResult.txt |grep alive"): 
        log.fail("The ip {0} is unreachable. Check why".format(instanceIP))
        logging.info("The ip {0} is unreachable. Check why".format(instanceIP))
        sys.exit()
    else:
        print "fping result: \n"
        subprocess.call("cat /export/ci/tools/autoRemoveAddCompute/pingResult.txt".format(instanceIP), shell=True)
        log.successFinal("The Test Has Finished SUCCESSFULLY")
        logging.info("The Test Has Finished SUCCESSFULLY")
            

    
def main():
    check_precondisions()
    getArguments()
    check_SRIOV_zone()
    #check_ifSRIOV()
    #connect()
    iLoIP = remove_compute()
    print "Got iLoIP= {0}".format(iLoIP)
    #add_compute(iLoIP)
    #print "Going to sleep 1 minute before SRIOV check"
    #time.sleep(60)
    #check_ifSRIOV()
    check_instance()

main()
