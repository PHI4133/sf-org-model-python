"""
    Install Salesforce CLI and append it to your environment path before running this script.
"""
import argparse
import logging
import re
import subprocess
import sys
import threading


# format logger
logging.basicConfig(format='%(message)s', level=logging.DEBUG)


def parse_args():
    """
        Function to parse required arguments.
        tests - required Apex tests to run against
        manifest - path to the package.xml file
        wait - number of minutes to wait for command to complete
        environment - Salesforce environment URL
        log - deploy log where the output of this script is being written to
            python ./deploy_metadata_sfdx.py --args | tee -a deploy_log.txt
            -a flag required to append to file during run-time
        pipeline - pipeline source (push or merge request)
        validate - set to True to run validation only deployment (for quick deploys)
        debug - print command rather than run
    """
    parser = argparse.ArgumentParser(description='A script to deploy metadata to Salesforce.')
    parser.add_argument('-t', '--tests', default='not,a,test')
    parser.add_argument('-m', '--manifest', default='manifest/package.xml')
    parser.add_argument('-w', '--wait', default=33)
    parser.add_argument('-e', '--environment')
    parser.add_argument('-l', '--log', default='deploy_log.txt')
    parser.add_argument('-p', '--pipeline', default='push')
    parser.add_argument('-v', '--validate', default=False, action='store_true')
    parser.add_argument('-d', '--debug', default=False, action='store_true')
    args = parser.parse_args()
    return args


def run_command(cmd):
    """
        Function to run the command using the native shell.
    """
    try:
        subprocess.run(cmd, check=True, shell=True)
    except subprocess.CalledProcessError:
        sys.exit(1)


def create_sf_link(sf_env, log, result):
    """
        Function to check the deploy log for the ID
        and build the URL.
    """
    pattern = r'Deploy ID: (.*)'
    classic_sf_path = '/changemgmt/monitorDeploymentsDetails.apexp?retURL=' +\
                        '/changemgmt/monitorDeployment.apexp&asyncId='

    # keep reading the log until the ID has been found
    deploy_id = None
    with open(log, 'r', encoding='utf-8') as deploy_file:
        while True:
            file_line = deploy_file.readline()
            match = re.search(pattern, file_line)
            # if regex is found, build the link and break the loop
            if match:
                deploy_id = match.group(1)
                break

    if deploy_id:
        sf_id = deploy_id[:-3]
        deploy_url = f'{sf_env}{classic_sf_path}{sf_id}'
        logging.info(deploy_url)
        result['deploy_id'] = deploy_id


def quick_deploy(deploy_id, wait):
    """
        Function to run a quick-deploy after
        a successful validation.
    """
    command = f'sf project deploy quick -i {deploy_id} -w {wait}'
    logging.info(command)
    logging.info('Running the quick-deployment.')
    run_command(command)


def main(testclasses, manifest, wait, environment, log, pipeline, validate, debug):
    """
        Main function to deploy metadata to Salesforce.
    """
    # Define the command
    command = (f'{"sf project deploy validate" if validate else "sf project deploy start"}'
                f' -x {manifest}'
                f' -l RunSpecifiedTests -t {testclasses} -w {wait} --verbose')
    logging.info(command)

    # Push pipelines which validate and quick-deploy must run tests during validation
    # in order to be eligible for a quick-deploy
    if validate and testclasses == 'not a test' and pipeline == 'push':
        logging.info('Not running a validation without test classes.')
        return

    if debug:
        return

    # Create deploy log
    with open(log, 'w', encoding='utf-8'):
        pass

    # Create result dictionary to store deploy_id
    result = {}

    # create and start threads
    read_thread = threading.Thread(target=create_sf_link, args=(environment, log, result))
    # set read thread to daemon so it automatically terminates when
    # the main program ends
    # ex: if package.xml is empty, no ID is created and the thread will continue to run
    read_thread.daemon = True
    read_thread.start()
    logging.info('Running the validation.' if validate else 'Running the deployment.')
    logging.info('Please open the URL to view real-time progress.')
    run_command(command)
    # run quick-deploy on push pipelines that validate
    if validate and pipeline == 'push':
        quick_deploy(result.get('deploy_id'), wait)


if __name__ == '__main__':
    inputs = parse_args()
    main(inputs.tests, inputs.manifest, inputs.wait, inputs.environment,
         inputs.log, inputs.pipeline, inputs.validate, inputs.debug)