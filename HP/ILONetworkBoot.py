#!/usr/bin/python
import argparse
import ilorest
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def converge_file(arguments):
    logger.info("Converging over given file.")
    f = open(arguments.hosts, 'r')

    for host in f:
        host = host.rstrip()  # Strip trailing whitespaces and newline.
        logger.info("HOST: %s -> Starting converge." % host)
        rest_obj = create_rest_object_from_host_and_login(host, arguments.username, arguments.password)
        set_temporary_boot_target(rest_obj, arguments.target)
        reset_host(rest_obj)
        logout_from_host(rest_obj)
    f.close()


def create_rest_object_from_host_and_login(host, username, password):
    logger.info("HOST: %s -> Creating REST object." % host)
    rest_obj = ilorest.rest_client(base_url=host, username=username, password=password, default_prefix='/rest/v1')
    rest_obj.login(auth="session")
    return rest_obj


def logout_from_host(rest_obj):
    logger.info("HOST: %s -> Logging out." % rest_obj.get_base_url())
    rest_obj.logout()


def reset_host(rest_obj):
    logger.info("HOST: %s -> Resetting host." % rest_obj.get_base_url())
    body = dict()
    body["Action"] = "Reset"
    body["ResetType"] = "ForceRestart"
    response = rest_obj.post(path="/rest/v1/Systems/1", body=body)
    if response.status != 200:
        logger.error("HOST: %s -> Unable to reset host. Exiting..." % rest_obj.get_base_url())
        sys.exit(1)
    logger.info("HOST: %s -> Reset host successful." % rest_obj.get_base_url())


def set_temporary_boot_target(rest_obj, boot_target):
    logger.info("HOST: %s -> Setting %s as temporary boot target." % (rest_obj.get_base_url(), boot_target))
    body = dict()
    body["Boot"] = dict()
    body["Boot"]["BootSourceOverrideEnabled"] = "Once"
    body["Boot"]["BootSourceOverrideTarget"] = boot_target
    response = rest_obj.patch(path="/rest/v1/Systems/1", body=body)
    if response.status != 200:
        logger.error("HOST: %s -> Setting %s as temporary boot target failed. Exiting..." % (rest_obj.get_base_url(), boot_target))
        sys.exit(1)
    logger.info("HOST: %s -> Setting %s as temporary boot target successful." % (rest_obj.get_base_url(), boot_target))


if __name__ == "__main__":
    logger.info("App: Set temporary boot target and reset host(s).")
    parser = argparse.ArgumentParser(description='Set network as temporary boot target and reset host(s).')
    parser.add_argument('--hosts', required=True, help='File containing the host(s) in line separated format')
    parser.add_argument('--username', required=True, help='Username to login to the ILO api')
    parser.add_argument('--password', required=True, help='Password to login to the ILO api')
    parser.add_argument('--target', default='Pxe', help='The target device to boot from.')
    args = parser.parse_args()
    converge_file(args)

