#  Copyright (c) 2015 SONATA-NFV, Paderborn University
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, UBIWHERE
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

import os
import tempfile
import argparse
import logging
import coloredlogs

from son.profile.experiment import ServiceExperiment, FunctionExperiment
from son.profile.sonpkg import extract_son_package, SonataServicePackage
from son.profile.helper import read_yaml

LOG = logging.getLogger(__name__)

"""
Configurations:
"""
SON_PKG_INPUT_DIR = "input_service"  # location of input package contents in args.work_dir
SON_PKG_SERVICE_DIR = "output_services"  # location of generated services in args.work_dir
SON_PKG_OUTPUT_DIR = "output_packages"  # location of generated packages in args.work_dir


class ProfileManager(object):
    """
    Main component class.
    """

    def __init__(self, args):
        self.service_experiments = list()
        self.function_experiments = list()
        # arguments
        self.args = args
        self.args.config = os.path.join(os.getcwd(), self.args.config)
        self.son_pkg_input_dir = os.path.join(self.args.work_dir, SON_PKG_INPUT_DIR)
        self.son_pkg_service_dir = os.path.join(self.args.work_dir, SON_PKG_SERVICE_DIR)
        self.son_pkg_output_dir = os.path.join(self.args.work_dir, SON_PKG_OUTPUT_DIR)
        # logging setup
        coloredlogs.install(level="DEBUG" if args.verbose else "INFO")
        LOG.info("SONATA profiling tool initialized")
        LOG.debug("Arguments: %r" % self.args)
        # try to load PED file
        self.ped = self._load_ped_file(self.args.config)
        self._validate_ped_file(self.ped)
        # unzip *.son package to be profiled and load its contents
        extract_son_package(self.ped, self.son_pkg_input_dir)
        self.son_pkg_input = SonataServicePackage.load(self.son_pkg_input_dir)
        # load and populate experiment specifications
        self.service_experiments, self.function_experiments = self._generate_experiment_specifications(self.ped)
        # generate experiment services (modified NSDs, VNFDs for each experiment run)
        self.generate_experiment_services()
        # package experiment services
        self.package_experiment_services()

    @staticmethod
    def _load_ped_file(ped_path):
        """
        Loads the specified PED file.
        :param ped_path: path to file
        :return: dictionary
        """
        yml = None
        try:
            yml = read_yaml(ped_path)
            if yml is None:
                raise BaseException("PED file YMAL error.")
        except:
            LOG.error("Couldn't load PED file %r. Abort." % ped_path)
            exit(1)
        # add path annotation to ped file (simpler handling of referenced artifacts)
        yml["ped_path"] = ped_path
        LOG.info("Loaded PED file %r." % ped_path)
        return yml

    @staticmethod
    def _validate_ped_file(input_ped):
        """
        Semantic validation of PED file contents.
        Check for all things we need to have in PED file.
        :param input_ped: ped dictionary
        :return: None
        """
        try:
            if "service_package" not in input_ped:
                raise BaseException("No service_package field found.")
            if "service_experiments" not in input_ped:
                raise BaseException("No service_experiments field found.")
            if "function_experiments" not in input_ped:
                raise BaseException("No function_experiments field found.")
            # TODO extend this when PED format is finally fixed
        except:
            LOG.exception("PED file verification error:")

    @staticmethod
    def _generate_experiment_specifications(input_ped):
        """
        Create experiment objects based on the contents of the PED file.
        :param input_ped: ped dictionary
        :return: service experiments list, function experiments list
        """
        service_experiments = list()
        function_experiments = list()

        # service experiments
        for e in input_ped.get("service_experiments"):
            e_obj = ServiceExperiment(e)
            e_obj.populate()
            service_experiments.append(e_obj)

        # function experiments
        for e in input_ped.get("function_experiments"):
            e_obj = FunctionExperiment(e)
            e_obj.populate()
            function_experiments.append(e_obj)

        return service_experiments, function_experiments

    def generate_experiment_services(self):
        """
        Generate SONATA service projects for each experiment and its configurations. The project is based
        on the contents of the service package referenced in the PED file and loaded to self.son_pkg_input.
        The generated project files are stored in self.args.work_dir.
        :return:
        """
        all_services = list()
        # generate service objects
        for e in self.service_experiments:
            all_services += e.generate_sonata_services(self.son_pkg_input)
        for e in self.function_experiments:
            all_services += e.generate_sonata_services(self.son_pkg_input)
        LOG.info("Generated %d services." % len(all_services))
        # write services to disk
        for s in all_services:
            s.write(self.son_pkg_service_dir)
        LOG.info("Wrote %d services to disk." % len(all_services))


    def package_experiment_services(self):
        # TODO use son-package to pack all previously generated service projects
        pass


def parse_args():
    """
    CLI interface definition.
    :return:
    """
    parser = argparse.ArgumentParser(
        description="Manage and control VNF and service profiling experiments.")

    parser.add_argument(
        "-v",
        "--verbose",
        help="Increases logging level to debug.",
        required=False,
        default=False,
        dest="verbose",
        action="store_true")

    parser.add_argument(
        "-c",
        "--config",
        help="PED file to be used for profiling run",
        required=True,
        dest="config")

    parser.add_argument(
        "--work-dir",
        help="Dictionary for generated artifacts, e.g., profiling packages. Will use a temporary folder as default.",
        required=False,
        default=tempfile.mkdtemp(),
        dest="work_dir")

    parser.add_argument(
        "--output-dir",
        help="Folder to collect measurements. Default: Current directory.",
        required=False,
        default=os.getcwd(),
        dest="output_dir")

    parser.add_argument(
        "--no-generation",
        help="Skip profiling package generation step.",
        required=False,
        default=False,
        dest="no_generation",
        action="store_true")

    parser.add_argument(
        "--no-execution",
        help="Skip profiling execution step.",
        required=False,
        default=False,
        dest="no_execution",
        action="store_true")

    return parser.parse_args()


def main():
    """
    Program entry point
    :return: None
    """
    args = parse_args()
    ProfileManager(args)
