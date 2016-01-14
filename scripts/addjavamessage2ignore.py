#!/usr/bin/python

import sys
import os
import pickle

import copy
import subprocess


'''
This script is written to a user to add new java messages that we can ignore during a log
scraping session.  In addition, the user can choose to remove old java messages that are okay
to ignore in the past but cannot be ignored anymore.  The user can edit a text file in the format of
keyName = general
Message = nfolds: nfolds cannot be larger than the number of rows (406).
KeyName = pyunit_cv_cars_gbm.py
Message = Caught exception: Illegal argument(s) for GBM model: GBM_model_python_1452503348770_2586.  Details: ERRR on field: _nfolds: nfolds must be either 0 or >1.
...
KeyName = pyunit_cv_cars_gbm.py
Message = Stacktrace: [water.exceptions.H2OModelBuilderIllegalArgumentException.makeFromBuilder(H2OModelBuilderIllegalArgumentException.java:19), \
water.api.ModelBuilderHandler.handle(ModelBuilderHandler.java:45), water.api.RequestServer.handle(RequestServer.java:617), \
water.api.RequestServer.serve(RequestServer.java:558), water.JettyHTTPD$H2oDefaultServlet.doGeneric(JettyHTTPD.java:616), \
water.JettyHTTPD$H2oDefaultServlet.doPost(JettyHTTPD.java:564), javax.servlet.http.HttpServlet.service(HttpServlet.java:755), \
javax.servlet.http.HttpServlet.service(HttpServlet.java:848), org.eclipse.jetty.servlet.ServletHolder.handle(ServletHolder.java:684)]; \
Values: {"messages":[{"_log_level":1,"_field_name":"_nfolds","_message":"nfolds must be either 0 or >1."},\
{"_log_level":5,"_field_name":"_tweedie_power","_message":"Only for Tweedie Distribution."},{"_log_level":5,"_field_name":"_max_after_balance_size",\
"_message":"Balance classes is false, hide max_after_balance_size"},{"_log_level":5,"_field_name":"_max_after_balance_size","_message":"Only used with balanced classes"},\
{"_log_level":5,"_field_name":"_class_sampling_factors","_message":"Class sampling factors is only applicable if balancing classes."}], "algo":"GBM", \
"parameters":{"_train":{"name":"py_3","type":"Key"},"_valid":null,"_nfolds":-1,"_keep_cross_validation_predictions":false,"_fold_assignment":"AUTO",\
"_distribution":"multinomial","_tweedie_power":1.5,"_ignored_columns":["economy_20mpg","fold_assignments","name","economy"],"_ignore_const_cols":true,\
"_weights_column":null,"_offset_column":null,"_fold_column":null,"_score_each_iteration":false,"_stopping_rounds":0,"_stopping_metric":"AUTO",\
"_stopping_tolerance":0.001,"_response_column":"cylinders","_balance_classes":false,"_max_after_balance_size":5.0,"_class_sampling_factors":null,\
"_max_confusion_matrix_size":20,"_checkpoint":null,"_ntrees":5,"_max_depth":5,"_min_rows":10.0,"_nbins":20,"_nbins_cats":1024,"_r2_stopping":0.999999,\
"_seed":-1,"_nbins_top_level":1024,"_build_tree_one_node":false,"_initial_score_interval":4000,"_score_interval":4000,"_sample_rate":1.0,\
"_col_sample_rate_per_tree":1.0,"_learn_rate":0.1,"_col_sample_rate":1.0}, "error_count":1}

'''

# --------------------------------------------------------------------
# Main program
# --------------------------------------------------------------------

g_test_root_dir = os.path.dirname(os.path.realpath(__file__)) # directory where we are running out code from
g_load_java_message_filename = "bad_java_messages_to_exclude.pickle" # default pickle filename that store previous java messages that we wanted to exclude
g_save_java_message_filename = "bad_java_messages_to_exclude.pickle" # pickle filename that we are going to store our java messages to
g_new_messages_to_exclude = ""  # user file that stores the new java messages to ignore
g_old_messages_to_remove = ""   # user file that stores java messages that are to be removed from the ignore list.
g_dict_changed = False          # True if dictionary has changed and False otherwise
g_java_messages_to_ignore_text_filename = "java_messages_to_ignore.txt" # store all rules for humans to read
g_print_java_messages = False

# store java bad messages that we can ignore.  The keys are "general",testnames that we
# want to add exclude messages for.  The values will all be a list of java messages that we want to ignore.
g_ok_java_messages = {}

def load_dict():
    global g_load_java_message_filename
    global g_ok_java_messages

    if os.path.isfile(g_load_java_message_filename):
        with open(g_load_java_message_filename,'rb') as ofile:
            g_ok_java_messages = pickle.load(ofile)
    else:   # no previous java messages to be excluded are found
        g_ok_java_messages = {}

def add_new_message():
    global g_new_messages_to_exclude
    global g_dict_changed

    new_message_dict = extract_message_to_dict(g_new_messages_to_exclude)
    if new_message_dict:
        g_dict_changed = True
        update_message_dict(new_message_dict,1) # update g_ok_java_messages with new message_dict, 1 to add, 2 to remove


def remove_old_message():    # remove java messages from ignored list if users desired it
    global g_old_messages_to_remove
    global g_dict_changed

    old_message_dict = extract_message_to_dict(g_old_messages_to_remove)

    if old_message_dict:
        g_dict_changed = True
        update_message_dict(old_message_dict,2)


def update_message_dict(message_dict,action):
    global g_ok_java_messages

    allKeys = g_ok_java_messages.keys()

    for key in message_dict.keys():
        if key in allKeys:  # key already exists, just add to it
            for message in message_dict[key]:

                if action == 1:
                    if message not in g_ok_java_messages[key]:
                        g_ok_java_messages[key].append(message)

                if action == 2:
                    if message in g_ok_java_messages[key]:
                        g_ok_java_messages[key].remove(message)
        else:   # new key here.  Can only add and cannot remove
            if action == 1:
                g_ok_java_messages[key] = message_dict[key]


'''
Function extract_message_to_dict is written to read in a file and generate a dictionary
structure out of it with key and value pairs.  The keys are test names and the values
are lists of java message strings associated with that test name where we are either
going to on to the existing java messages to ignore or remove them.
'''
def extract_message_to_dict(filename):
    message_dict = {}

    if os.path.isfile(filename):
        # open file to read in new exclude messages if it exists
        with open(filename,'r') as wfile:
            eof_reached = False
            while  not eof_reached:
                each_line = wfile.readline()

                if not each_line:
                    break;

                allKeys = message_dict.keys()
                key = ""

                # found a test name or general with values to follow
                if "keyname" in each_line.lower():  # name of test file or the word "general"
                    temp_strings = each_line.strip().split('=')

                    if (len(temp_strings) > 1): # make sure the line is formatted sort of correctly
                        key = temp_strings[1].strip()

                        # next line or so should contain the messages for the key we just found.
                        val = ""
                        while not eof_reached:
                            next_line = wfile.readline()

                            if not next_line:
                                eof_reached = True
                                break


                            if "message" in next_line.lower():
                                temp_mess = next_line.strip().split('=')

                                if (len(temp_mess) > 1):
                                    val = temp_mess[1].strip()
                                    break  # found the message and quit for now

                        if (len(val) > 0):    # got a valid message here
                            if (key in allKeys) and (val not in message_dict[key]):
                                message_dict[key].append(val)   # only include this message if it has not been added before
                            else:
                                message_dict[key] = [val]
    return message_dict


def save_dict():
    global g_ok_java_messages
    global g_save_java_message_filename
    global g_dict_changed

    if g_dict_changed:
        with open(g_save_java_message_filename,'wb') as ofile:
            pickle.dump(g_ok_java_messages,ofile)

def print_dict():
    global g_ok_java_messages
    global g_java_messages_to_ignore_text_filename

    allKeys = sorted(g_ok_java_messages.keys())

    with open(g_java_messages_to_ignore_text_filename,'w') as ofile:
        for key in allKeys:

            for mess in g_ok_java_messages[key]:
                ofile.write('KeyName: '+key+'\n')
                ofile.write('Message: '+mess+'\n')

            print('KeyName: ',key)
            print('Message: ',g_ok_java_messages[key])
            print('\n')



def parse_args(argv):
    global g_new_messages_to_exclude
    global g_old_messages_to_remove
    global g_load_java_message_filename
    global g_save_java_message_filename
    global g_print_java_messages

    i = 1
    while (i < len(argv)):
        s = argv[i]

        if (s == "--inputfileadd"):    # input text file where new java messages are stored
            i += 1
            if (i > len(argv)):
                usage()
            g_new_messages_to_exclude = argv[i]
        elif (s == "--inputfilerm"):     # input text file containing java messages to be removed from the ignored list
            i += 1
            if (i > len(argv)):
                usage()
            g_old_messages_to_remove = argv[i]
        elif (s == "--loadjavamessage"): # load previously saved java message pickle file before performing update
            i += 1
            if i > len(argv):
                usage()
            g_load_java_message_filename = argv[i]
        elif (s == "--savejavamessage"):    # save updated java message in this file
            i += 1
            if (i > len(argv)):
                usage()
            g_save_java_message_filename = argv[i]
        elif (s == '--printjavamessage'):   # will print java message out to console and save in a file
            g_print_java_messages = True
        else:
            unknown_arg(s)

        i += 1


def usage():
    global g_script_name

    print("")
    print("Usage:  " + g_script_name + " [...options...]")
    print("")
    print("    --inputfileadd      file name where the new java messages to ignore are stored in  Must present.")
    print("")
    print("    --inputfilerm       file name where the java messages are removed from the ignored list.")
    print("")
    print("    --loadjavamessage   file name ending in .pickle that stores the dict structure that contains java messages to include.")
    print("")
    print("    --savejavamessage   file name ending in .pickle that save the final dict structure after update.")
    print("")
    print("    --printjavamessage   print java ignored java messages on console and save into a text file.")
    print("")
    sys.exit(1)


def unknown_arg(s):
    print("")
    print("ERROR: Unknown argument: " + s)
    print("")
    usage()
        
def main(argv):
    """
    Main program.

    @return: none
    """
    global g_script_name
    global g_test_root_dir
    global g_new_messages_to_exclude
    global g_old_messages_to_remove
    global g_load_java_message_filename
    global g_save_java_message_filename
    global g_print_java_messages
    global g_java_messages_to_ignore_text_filename


    g_script_name = os.path.basename(argv[0])   # get name of script being run.


    # Override any defaults with the user's choices.
    parse_args(argv)

    g_load_java_message_filename = os.path.join(g_test_root_dir,g_load_java_message_filename)
    load_dict() # load previously stored java messages to exclude dictionary

    if len(g_new_messages_to_exclude) > 0:
        g_new_messages_to_exclude = os.path.join(g_test_root_dir,g_new_messages_to_exclude)
        add_new_message()   # add new java messages to exclude to dictionary

    if len(g_old_messages_to_remove) > 0:
        g_old_messages_to_remove = os.path.join(g_test_root_dir,g_old_messages_to_remove)
        remove_old_message()    # remove java messages from ignored list if users desired it

    g_save_java_message_filename = os.path.join(g_test_root_dir,g_save_java_message_filename)
    save_dict()

    if g_print_java_messages:
        g_java_messages_to_ignore_text_filename = os.path.join(g_test_root_dir,g_java_messages_to_ignore_text_filename)
        print_dict()






if __name__ == "__main__":
    main(sys.argv)
