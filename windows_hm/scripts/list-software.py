import _winreg

#import win32com.client 
#from collections import OrderedDict
#import sys
#sys.path.append('"C:\\Python27_x86"')
#strComputer = "." 
#objWMIService = win32com.client.Dispatch("WbemScripting.SWbemLocator") 
#objSWbemServices = objWMIService.ConnectServer(strComputer,"root\cimv2") 
#colItems = objSWbemServices.ExecQuery("Select * from Win32_Product") 
#for objItem in colItems: 
#    print "Caption: ", objItem.Caption 
#    print "Description: ", objItem.Description 
#    print "Identifying Number: ", objItem.IdentifyingNumber 
#    print "Install Date: ", objItem.InstallDate 
#    print "Install Date 2: ", objItem.InstallDate2 
#    print "Install Location: ", objItem.InstallLocation 
#    print "Install State: ", objItem.InstallState 
#    print "Name: ", objItem.Name 
#    print "Package Cache: ", objItem.PackageCache 
#    print "SKU Number: ", objItem.SKUNumber 
#    print "Vendor: ", objItem.Vendor 
#    print "Version: ", objItem.Version 
 

UNINSTALL_PATH1 = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
UNINSTALL_PATH2 = "SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"

class Package:
    def __init__(self):
        self.displayName = "Unknown"
        self.displayVersion = "Unknown"
        self.estimatedSize = "Unknown"
        self.installDate = "Unknown"

    def __cmp__(self, other):
        return cmp(self.displayName, other.displayName)

def get_installed_packages_for_keypath(keypath):
    key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, keypath,
                          0, _winreg.KEY_READ)


    packages = []
    
    i = 0
    while True:
        try:
            subkey_str = _winreg.EnumKey(key, i)
            i += 1
            subkey = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, keypath + "\\" + subkey_str, 
                          0, _winreg.KEY_READ | _winreg.KEY_WOW64_64KEY)
            #print subkey_str

            j = 0

            package = Package()
            while True:
                try:
                    subvalue = _winreg.EnumValue(subkey, j)
                    j += 1
                    
                    

                    _val, _data, _type = subvalue
                    if _val == "DisplayName":
                        package.displayName = _data
                    elif _val == "DisplayVersion":
                        package.displayVersion = _data
                    elif _val == "EstimatedSize":
                        package.estimatedSize = _data
                    elif _val == "InstallDate":
                        package.installDate = _data

                except WindowsError as e:
                    break
	    if package.displayName != "Unknown":
                packages.append(package) 
        except WindowsError as e:
            break

    return packages 



if __name__=="__main__":
    package_list1 = get_installed_packages_for_keypath(UNINSTALL_PATH1)
    package_list2 = get_installed_packages_for_keypath(UNINSTALL_PATH2)
    package_list1.extend(package_list2)
    package_list1.sort()

    for package in package_list1:
        print "%s\t%s\t%s" % (package.displayName, package.displayVersion, package.installDate)