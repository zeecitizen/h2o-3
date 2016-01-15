#!/usr/bin/python

import sys
import os
import json
import pickle

import copy
import subprocess


'''
This version is different from the other ones in the sense that it will take the name of the file
but will save the file in the directory where this script is run from.  In addition, we added in the view
name in which the jenkin job is located.  This is needed in order to reliably access the console output for
some reason.  I was able to run without it before if I ran it from my own computer.  But once I am in the git
tracked repos, I was not able to get the correct console output for some reason.
'''

'''
TODOs:
1. separately write the java messages for failed tests and tests that passed. --DONE 1/13/16.
2. add option to argument list so that users can choose to upload personalized
bad Java messages to exclude.  If options not specified, default files will be
used to stored the bad Java messages to include.     --DONE 1/13/16.
3. Implement the code to support general Java messages to exclude and support Java messages
to exclude per test name;    --DONE 1/13/16.
4. Implement the code to support loading Java messages to exclude from default or user
specified files.     --DONE 1/13/16.
5. Generate a consolidated log for all failed tests to send to user
6. Come up with a better way to generate a mail message to inform user of failed tests.
'''
# --------------------------------------------------------------------
# Main program
# --------------------------------------------------------------------

g_test_root_dir = os.path.dirname(os.path.realpath(__file__)) # directory where we are running out code from
g_script_name = ''

g_node_name = "Building remotely on"   # the very next string is the name of the computer node that ran the test
g_git_hash_branch = "Checking out Revision"    # next string is git hash, and the next one is (origin/branch)
g_build_timeout = "Build timed out"             # phrase when tests run too long
g_build_success = ["Finished: SUCCESS",'BUILD SUCCESSFUL']           # sentence at the end that guarantee build success

g_build_success_tests = ['generate_rest_api_docs.py','generate_java_bindings.py'] # two functions that are usually performed after build success
g_build_id_text = 'Build id is'
g_view_name = ''

g_temp_filename = os.path.join(g_test_root_dir,'tempText')

g_output_filename_failed_tests = os.path.join(g_test_root_dir,'failedMessage_failed_tests.log')
g_output_filename_passed_tests = os.path.join(g_test_root_dir,'failedMessage_passed_tests.log')
g_output_pickle_filename = os.path.join(g_test_root_dir,'failedMessage.pickle.log')

g_failed_test_info_dict = {}
g_failed_test_info_dict["7.build_failure"] = "No"   # initialize build_failure with no by default

g_weekdays = 'Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday'

g_months = 'January, Feburary, March, May, April, May, June, July, August, September, October, November, December'

g_failure_occurred = False  # denote when failure actually occurred

g_failed_jobs = []  # record job names of failed jobs
g_failed_job_java_message_types = []    # java bad message types (can be WARN:, ERRR:, FATAL:, TRACE:)
g_failed_job_java_messages = []  # record failed job java message

g_success_jobs = []  # record job names of passed jobs
g_success_job_java_message_types = []
g_success_job_java_messages = [] # record of successful jobs bad java messages

# text you will find before you can find your java_*_*.out.txt 
g_before_java_file = ["H2O Cloud", "Node", "started with output file"]

g_java_filenames = []   # contains all java filenames for us to mine
g_java_message_type = ["WARN:", "ERRR:", "FATAL:", "TRACE:"]

g_java_general_bad_message_types = []
g_java_general_bad_messages = []    # store java messages that are not associated with any tests

g_jenkins_url = ''

# denote when we are in a test during java text scanning
g_current_testname = ''

g_java_start_text = 'STARTING TEST:'    # test being started in java

g_ok_java_messages = {} # store java bad messages that we can ignore
g_java_message_pickle_filename = "bad_java_messages_to_exclude.pickle"  # pickle file that store the dictionary structure that include Java error message to exclude
g_build_failed_message = ["Finished: FAILURE".lower(),'BUILD FAILED'.lower()]   # something has gone wrong.  No tests are performed.
g_summary_text_filename = ""    # filename to store the summary file to be sent to user.

'''
The sole purpose of this function is to enable us to be able to call
any function that is specified as the first argument using the argument
list specified in second argument.
'''
def perform(function_name, *arguments):
    return function_name(*arguments)


'''
This function is written to remove extra characters before the actual string we are
looking for.  The Jenkins console output is encoded using utf-8.  However, the stupid
redirect function can only encode using ASCII.  I have googled for half a day with no
results to how.  Hence, we are going to the heat and just manually get rid of the junk.
'''
def extract_true_string(string_content):
    startL,found,endL = string_content.partition('[0m')

    if found:
        return endL
    else:
        return string_content

"""
Function find_time is written to extract the timestamp when a job is built.
"""
def find_time(each_line,temp_func_list):
    global g_weekdays
    global g_months
    global g_failed_test_info_dict
    
    temp_strings = each_line.strip().split()

    if (len(temp_strings) > 2):
        if (temp_strings[0] in g_weekdays) and (temp_strings[1] in g_months):
            g_failed_test_info_dict["3.timestamp"] = each_line.strip()
            temp_func_list.remove(find_time)    # found timestamp, don't need to look again for it

    return True
            
   
def find_node_name(each_line,temp_func_list):
    global g_node_name
    global g_failed_test_info_dict

    if g_node_name in each_line:
        temp_strings = each_line.split()

        g_failed_test_info_dict["6.node_name"] = extract_true_string(temp_strings[4])
        temp_func_list.remove(find_node_name)

    return True


def find_git_hash_branch(each_line,temp_func_list):
    global g_git_hash_branch
    global g_failed_test_info_dict

    if g_git_hash_branch in each_line:
        temp_strings = each_line.split()
        g_failed_test_info_dict["4.git_hash"] = temp_strings[3]
        g_failed_test_info_dict["5.git_branch"] = temp_strings[4]

        temp_func_list.remove(find_git_hash_branch)

    return True


def find_build_timeout(each_line,temp_func_list):
    global g_build_timeout
    global g_failed_test_info_dict
    global g_failure_occurred

    if g_build_timeout in each_line:
        g_failed_test_info_dict["8.build_timeout"] = 'Yes'
        g_failure_occurred = True
        return False
    else:
        return True

def find_build_failure(each_line,temp_func_list):
    global g_build_success
    global g_build_success_tests
    global g_failed_test_info_dict
    global g_failure_occurred
    global g_build_failed_message
    # if ((g_build_success[0] in each_line) or (g_build_success[1] in each_line) or (g_build_success_tests[0] in each_line) or (g_build_success_tests[1] in each_line)):
    #     g_failed_test_info_dict["7.build_failure"] = 'No'
    #     temp_func_list.remove(find_build_failure)

    for ind in range(0,len(g_build_failed_message)):
        if g_build_failed_message[ind] in each_line.lower():
            if ((ind == 0) and (len(g_failed_jobs) > 0)):
                continue
            else:
                g_failure_occurred = True
                g_failed_test_info_dict["7.build_failure"] = 'Yes'
                temp_func_list.remove(find_build_failure)
                return False

    return True


"""
Function find_java_filename will go through the console output and find the
java filename that we need to comb through and find all the error/warning
messages.
"""
def find_java_filename(each_line,temp_func_list):
    global g_before_java_file
    global g_java_filenames

    for each_word in g_before_java_file:
        if (each_word not in each_line):
            return True

    # line contains the name and location of java txt output filename
    temp_strings = each_line.split()
    g_java_filenames.append(temp_strings[-1])

    return True


def find_build_id(each_line,temp_func_list):
    global g_before_java_file
    global g_java_filenames
    global g_build_id_text
    global g_jenkins_url
    global g_output_filename
    global g_output_pickle_filename


    if g_build_id_text in each_line:
        startStr,found,endStr = each_line.partition(g_build_id_text)
        g_failed_test_info_dict["2.build_id"] = endStr.strip()

        temp_func_list.remove(find_build_id)
        g_jenkins_url = os.path.join('http://',g_jenkins_url,'view',g_view_name,'job',g_failed_test_info_dict["1.jobName"],g_failed_test_info_dict["2.build_id"],'artifact')


    return True

# global list of all functions that are performed extracting new build information.
g_build_func_list = [find_time,find_node_name,find_build_id,find_git_hash_branch,find_build_timeout,find_build_failure,find_java_filename]


def update_test_dict(each_line):
    global g_ignore_test_names
    global g_failed_jobs
    global g_failed_job_durations
    global g_failed_job_java_messages
    global g_failure_occurred

    temp_strings = each_line.split()

    if (len(temp_strings) >= 5) and ("FAIL" in temp_strings[0]) and ("FAILURE" not in temp_strings[0]):   # found failed test
        test_name = temp_strings[3]
        g_failed_jobs.append(test_name)
        g_failed_job_java_messages.append([]) # insert empty java messages for now
        g_failed_job_java_message_types.append([])
        g_failure_occurred = True

    return True


'''
This function is written to extract the error messages from console output and
possible from the java_*_*.out to warn users of potentially bad runs.

'''
def extract_test_results(resource_url):
    global g_test_root_dir
    global g_temp_filename
    global g_output_filename
    global g_build_func_list

    temp_func_list = copy.copy(g_build_func_list)

    if os.path.isfile(g_temp_filename):
        console_file = open(g_temp_filename,'r')  # open file for business

        for each_line in console_file:
            each_line.strip()

            for each_function in temp_func_list:
                to_continue = perform(each_function,each_line,temp_func_list)

                if not(to_continue):
                    break

            if not(to_continue):    # something like build failure or built time out has occurred.  Stop
                break
            else:
                update_test_dict(each_line)  # update the test_dict with new tests if found

        console_file.close()
    else:
        print "Error: console output file "+g_temp_filename + " does not exist."
        sys.exit(1)


'''
This function is written to extract the console output that has already been stored
in a text file in a remote place and saved it in a local directory that we have accessed
to.  We want to be able to read in the local text file and proces it.
'''
def get_console_out(url_string):
    global g_temp_filename

    full_command = 'curl ' + url_string + ' > ' + g_temp_filename
    subprocess.call(full_command,shell=True)


def extract_job_build_url(url_string):
    global g_failed_test_info_dict
    global g_jenkins_url
    global g_view_name
    
    tempString = url_string.strip('/').split('/')

    if len(tempString) < 6:
        print "Illegal URL resource address.\n"
        sys.exit(1)
        
    g_failed_test_info_dict["1.jobName"] = tempString[6]
        
    g_jenkins_url = tempString[2]
    g_view_name = tempString[4]
    

def grab_java_message():
    global g_temp_filename
    global g_current_testname
    global g_java_start_text
    global g_ok_java_messages
    global g_java_general_bad_messages
    global g_java_general_bad_message_types
    global g_failure_occurred
    global  g_java_message_type

    java_messages = []
    java_message_types = []

    if os.path.isfile(g_temp_filename):
        java_file = open(g_temp_filename,'r')

#        linecount = 0
        for each_line in java_file:
#            linecount=linecount+1
            if (g_java_start_text in each_line):
                startStr,found,endStr = each_line.partition(g_java_start_text)

                if len(found) > 0:   # a new test is being started.  Save old info and move on
                    if len(g_current_testname) > 0:
                        associate_test_with_java(g_current_testname,java_messages,java_message_types)
        
                    g_current_testname = endStr.strip() # record the test name
                    
                    java_messages = []
                    java_message_types = []
        
            temp_strings = each_line.strip().split()   # grab each line and process

            if ((len(temp_strings) > 5) and (temp_strings[5] in g_java_message_type)):  # find one of the strings of interest

                startStr,found,endStr = each_line.strip().partition(temp_strings[5])    # can be WARN,ERRR,FATAL,TRACE

                if found and (len(endStr.strip()) > 0):
                    tempMessage = endStr.strip()
                    if (tempMessage not in g_ok_java_messages["general"]):  # found new bad messages

                        if (len(g_current_testname) == 0):    # java message not associated with any test name
                            g_java_general_bad_messages.append(tempMessage)
                            g_java_general_bad_message_types.append(temp_strings[5])
                            g_failure_occurred = True
                        else:   # java message found during a test
                            write_test = False  # do not include java message for test if False
                            if g_current_testname in g_ok_java_messages.keys(): # test name associated with ignored Java messages
                                if tempMessage not in g_ok_java_messages[g_current_testname]:
                                    write_test = True
                            else:
                                write_test = True

                            if write_test:
                                java_messages.append(tempMessage)
                                java_message_types.append(temp_strings[5])
                                g_failure_occurred = True
#        print "line read ",linecount
                            


'''
Function associate_test_with_java is written to associate bad java messages
with failed or sucessful jobs.
'''
def associate_test_with_java(testname, java_message,java_message_type):
    global g_failed_jobs  # record job names of failed jobs
    global g_failed_job_java_messages # record failed job java message
    global g_failed_job_java_message_types

    global g_success_jobs # record job names of passed jobs
    global g_success_job_java_messages # record of successful jobs bad java messages
    global g_success_job_java_message_types

    if len(java_message) > 0:
        if (testname in g_failed_jobs):
            message_index = g_failed_jobs.index(testname)
            g_failed_job_java_messages[message_index] = java_message
            g_failed_job_java_message_types[message_index] = java_message_type
        else:   # job has been sucessfully executed but something still has gone wrong
            g_success_jobs.append(testname)
            g_success_job_java_messages.append(java_message)
            g_success_job_java_message_types.append(java_message_type)

"""
Function extract_java_messages is written to loop through java.out.txt and
extract potentially dangerous WARN/ERRR/FATAL messages associated with a test.
The test may even pass but something terrible has actually happened.
"""
def extract_java_messages():
    global g_jenkins_url
    global g_failed_test_info_dict
    global g_java_filenames

    global g_failed_jobs  # record job names of failed jobs
    global g_failed_job_java_messages # record failed job java message
    global g_failed_job_java_message_types

    global g_success_jobs # record job names of passed jobs
    global g_success_job_java_messages # record of successful jobs bad java messages
    global g_success_job_java_message_types
   
    global g_java_general_bad_messages  # store java error messages when no job is running
    global g_java_general_bad_message_types # store java error message types when no job is running.



    if (len(g_failed_jobs) > 0):  # artifacts available only during failure of some sort
        for fname in g_java_filenames:  # grab java message from each java_*_*_.out file
            temp_strings = fname.split('/')

            start_url = g_jenkins_url

            for windex in range(6,len(temp_strings)):
                start_url = os.path.join(start_url,temp_strings[windex])
            try:    # first java file path is different.  Can ignore it.
                get_console_out(start_url)  # get java text and save it in local directory for processing
                grab_java_message()         # actually process the java text output and see if we found offensive stuff
            except:
                pass



    # build up the dict structure that we are storing our data in
    if len(g_failed_jobs) > 0:
        g_failed_test_info_dict["failed_tests_info *********"] = [g_failed_jobs,g_failed_job_java_messages,g_failed_job_java_message_types]
    if len(g_success_jobs) > 0:
        g_failed_test_info_dict["passed_tests_info *********"] = [g_success_jobs,g_success_job_java_messages,g_success_job_java_message_types]

    if len(g_java_general_bad_messages) > 0:
        g_failed_test_info_dict["9.general_bad_java_messages"] = [g_java_general_bad_messages,g_java_general_bad_message_types]


'''
This file is written to load the dictionary structure that we have stored before from a file and potentially updated it with
new build information as time goes by.

'''
def save_dict():

    global g_test_root_dir
    global g_output_filename_failed_tests
    global g_output_filename_passed_tests
    global g_output_pickle_filename
    global g_failed_test_info_dict


    if "2.build_id" not in g_failed_test_info_dict.keys():
        build_id = 'unknown'
    else:
        build_id = g_failed_test_info_dict["2.build_id"]

    g_output_filename_failed_tests = g_output_filename_failed_tests+'_build_'+build_id+'_failed_tests.log'
    g_output_filename_passed_tests = g_output_filename_passed_tests+'_build_'+build_id+'_passed_tests.log'
    g_output_pickle_filename = g_output_pickle_filename+'_build_'+build_id+'.pickle'

    allKeys = sorted(g_failed_test_info_dict.keys())
    with open(g_output_pickle_filename,'wb') as test_file:
        pickle.dump(g_failed_test_info_dict,test_file)
        test_file.close()

    # write out the failure report as text into a text file
    text_file_failed_tests = open(g_output_filename_failed_tests,'w')
    text_file_passed_tests = None
    allKeys = sorted(g_failed_test_info_dict.keys())
    write_passed_tests = False

    if ("passed_tests_info *********" in allKeys):
        text_file_passed_tests = open(g_output_filename_passed_tests,'w')
        write_passed_tests = True

    for keyName in allKeys:
        val = g_failed_test_info_dict[keyName]
        if isinstance(val,list):    # writing one of the job lists
            if (len(val) == 3):     # it is a message for a test
                if keyName == "failed_tests_info *********":
                    write_test_java_message(keyName,val,text_file_failed_tests)

                if keyName == "passed_tests_info *********":
                    write_test_java_message(keyName,val,text_file_passed_tests)
            elif (len(val) == 2):                   # it is a general bad java message
                write_java_message(keyName,val,text_file_failed_tests)
                if write_passed_tests:
                    write_java_message(keyName,val,text_file_passed_tests)
        else:
            write_general_build_message(keyName,val,text_file_failed_tests)
            if write_passed_tests:
                write_general_build_message(keyName,val,text_file_passed_tests)

    text_file_failed_tests.close()
    if write_passed_tests:
        text_file_passed_tests.close()

def write_general_build_message(key,val,text_file):
    text_file.write(key+": ")
    text_file.write(val)
    text_file.write('\n\n')

def write_test_java_message(key,val,text_file):
    global g_failed_jobs

    text_file.write(key)
    text_file.write('\n')

    # val is a tuple of 3 tuples
    for index in range(len(val[0])):

        if ((val[0][index] in g_failed_jobs) or ((val[0][index] not in g_failed_jobs) and (len(val[1][index]) > 0))):
            text_file.write("\nTest Name: ")
            text_file.write(val[0][index])
            text_file.write('\n')

        if (len(val[1][index]) > 0) and (len(val) >= 3):
            text_file.write("Java Message Type and Message: \n")
            for eleIndex in range(len(val[1][index])):
                text_file.write(val[2][index][eleIndex]+" ")
                text_file.write(val[1][index][eleIndex])
                text_file.write('\n')

    text_file.write('\n')
    text_file.write('\n')

def update_summary_file():
    global g_summary_text_filename
    global g_output_filename_failed_tests
    global g_output_filename_passed_tests

    with open(g_summary_text_filename,'a') as tempfile:
        write_file_content(tempfile,g_output_filename_failed_tests)
        write_file_content(tempfile,g_output_filename_passed_tests)


def write_file_content(fhandle,file2read):
    if os.path.isfile(file2read):

        # write summary of failed tests logs
        with open(file2read,'r') as tfile:
            fhandle.write('============ Content of '+ file2read)
            fhandle.write('\n')
            fhandle.write(tfile.read())
            fhandle.write('============================================================================ \n\n')



def write_java_message(key,val,text_file):

    text_file.write(key)
    text_file.write('\n')

    if (len(val[0]) > 0) and (len(val) >= 3):
        for index in range(len(val[0])):
            text_file.write("Java Message Type: ")
            text_file.write(val[1][index])
            text_file.write('\n')

            text_file.write("Java Message: ")

            for jmess in val[2][index]:
                text_file.write(jmess)
                text_file.write('\n')

        text_file.write('\n \n')


def load_java_messages_to_ignore():
    global g_ok_java_messages
    global g_java_message_pickle_filename

    if os.path.isfile(g_java_message_pickle_filename):
        with open(g_java_message_pickle_filename,'rb') as tfile:
            g_ok_java_messages = pickle.load(tfile)
    else:
        g_ok_java_messages["general"] = []


def main(argv):
    """
    Main program.

    @return: none
    """
    global g_script_name
    global g_test_root_dir
    global g_temp_filename
    global g_output_filename_failed_tests
    global g_output_filename_passed_tests
    global g_output_pickle_filename
    global g_failure_occurred
    global g_failed_test_info_dict
    global g_java_message_pickle_filename
    global g_summary_text_filename

    if len(argv) < 3:
        print "Must resource url like http://mr-0xa1:8080/view/wendy_jenkins/job/h2o_regression_pyunit_medium_large/lastBuild/consoleFull, filename of summary text, filename (optional ending in .pickle) to retrieve Java error messages to exclude.\n"
        sys.exit(1)
    else:   # we may be in business
        g_script_name = os.path.basename(argv[0])   # get name of script being run.
        resource_url = argv[1]

        g_temp_filename = os.path.join(g_test_root_dir,'tempText')
        g_summary_text_filename = os.path.join(g_test_root_dir,argv[2])

        if len(argv) == 4:
            g_java_message_pickle_filename  = argv[3]

        get_console_out(resource_url)   # save remote console output in local directory
        extract_job_build_url(resource_url) # extract the job name of build id for identification purposes

        log_filename = g_failed_test_info_dict["1.jobName"]
        log_pickle_filename = g_failed_test_info_dict["1.jobName"]

        # pickle file that store bad Java messages that we can ignore.
        g_java_message_pickle_filename = os.path.join(g_test_root_dir,g_java_message_pickle_filename)
        g_output_filename_failed_tests = os.path.join(g_test_root_dir,log_filename)
        g_output_filename_passed_tests = os.path.join(g_test_root_dir,log_filename)
        g_output_pickle_filename = os.path.join(g_test_root_dir,log_pickle_filename)

        load_java_messages_to_ignore()          # load g_ok_
        extract_test_results(resource_url)      # grab the console text and stored the failed tests.
        extract_java_messages()     # grab dangerous java messages that we found for the various tests
        if ((len(g_failed_jobs) > 0) or (g_failed_test_info_dict["7.build_failure"]=='Yes')):
            g_failure_occurred = True

        if g_failure_occurred:
            save_dict() # save the dict structure in a pickle file and a text file when failure is detected
            update_summary_file()   # join together log files
            print g_failed_test_info_dict["1.jobName"]+' build '+g_failed_test_info_dict["2.build_id"]
        else:
            print ""


if __name__ == "__main__":
    main(sys.argv)
