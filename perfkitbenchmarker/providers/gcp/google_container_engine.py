# Copyright 2017 PerfKitBenchmarker Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Contains classes/functions related to GKE (Google Container Engine)."""

import os

from perfkitbenchmarker import container_service
from perfkitbenchmarker import flags
from perfkitbenchmarker import kubernetes_helper
from perfkitbenchmarker import providers
from perfkitbenchmarker.providers.gcp import gce_virtual_machine
from perfkitbenchmarker.providers.gcp import util

FLAGS = flags.FLAGS

NVIDIA_DRIVER_SETUP_DAEMON_SET_SCRIPT = 'https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/k8s-1.8/device-plugin-daemonset.yaml'


class GkeCluster(container_service.KubernetesCluster):

  CLOUD = providers.GCP

  @staticmethod
  def _GetRequiredGkeEnv():
    env = os.environ.copy()
    env['CLOUDSDK_CONTAINER_USE_APPLICATION_DEFAULT_CREDENTIALS'] = 'true'
    return env

  def __init__(self, spec):
    super(GkeCluster, self).__init__(spec)
    self.project = spec.vm_spec.project

  def _Create(self):
    """Creates the cluster."""
    if self.gpu_count:
      gcp_specific_gpu_type = (gce_virtual_machine.
                               GPU_TYPE_TO_INTERAL_NAME_MAP[self.gpu_type])
      # TODO(ferneyhough): Make cluster version a flag, and allow it
      # to be specified in the spec (this will require a new spec class
      # for google_container_engine however).
      cmd = util.GcloudCommand(
          self, 'alpha', 'container', 'clusters', 'create', self.name,
          '--enable-kubernetes-alpha', '--cluster-version', '1.8.1-gke.1')

      cmd.flags['accelerator'] = 'type={0},count={1}'.format(
          gcp_specific_gpu_type,
          self.gpu_count)

    else:
      cmd = util.GcloudCommand(
          self, 'container', 'clusters', 'create', self.name)

    cmd.flags['num-nodes'] = self.num_nodes
    cmd.flags['machine-type'] = self.machine_type

    cmd.Issue(timeout=600, env=self._GetRequiredGkeEnv())

  def _PostCreate(self):
    """Acquire cluster authentication."""
    cmd = util.GcloudCommand(
        self, 'container', 'clusters', 'get-credentials', self.name)
    env = self._GetRequiredGkeEnv()
    env['KUBECONFIG'] = FLAGS.kubeconfig
    cmd.IssueRetryable(env=env)

    if self.gpu_count:
      kubernetes_helper.CreateFromFile(NVIDIA_DRIVER_SETUP_DAEMON_SET_SCRIPT)

  def _Delete(self):
    """Deletes the cluster."""
    cmd = util.GcloudCommand(
        self, 'container', 'clusters', 'delete', self.name)
    cmd.Issue()

  def _Exists(self):
    """Returns True if the cluster exits."""
    cmd = util.GcloudCommand(
        self, 'container', 'clusters', 'describe', self.name)
    _, _, retcode = cmd.Issue(suppress_warning=True)
    return retcode == 0
