"""
Contains an abstract base class that supports different ML models.
"""
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

__author__ = "Bharath Ramsundar and Joseph Gomes, modified by Qingyuan Feng"
__copyright__ = "Copyright 2018, Simon Fraser University"
__license__ = "MIT"

import pdb
import numpy as np
import os
import shutil
import tempfile
from sklearn.base import BaseEstimator
from dcCustom.data import pad_features
from dcCustom.trans import undo_transforms
from deepchem.utils.save import log
from dcCustom.utils.evaluate import Evaluator

class Model(BaseEstimator):
  """
  Abstract base class for different ML models.
  """

  def __init__(self,
               model_instance=None,
               model_dir=None,
               verbose=True,
               prot_desc_dict=None,
               prot_desc_length=None,
               restore_model=False,
               input_protein=True,
               **kwargs):
    """Abstract class for all models.
    Parameters:
    -----------
    model_instance: object
      Wrapper around ScikitLearn/Keras/Tensorflow model object.
    model_dir: str
      Path to directory where model will be stored.
    """
    self.model_dir_is_temp = False
    if model_dir is not None:
      if not restore_model:
        if os.path.exists(model_dir):
          shutil.rmtree(model_dir)
        os.makedirs(model_dir)
      else:
        assert os.path.exists(model_dir)
    else:
      assert not restore_model
      model_dir = tempfile.mkdtemp()
      self.model_dir_is_temp = True
    self.model_dir = model_dir
    self.model_instance = model_instance
    self.model_class = model_instance.__class__

    self.verbose = verbose
    self.prot_desc_dict = prot_desc_dict
    self.prot_desc_length = prot_desc_length
    self.input_protein = input_protein

  def __del__(self):
    if 'model_dir_is_temp' in dir(self) and self.model_dir_is_temp:
      shutil.rmtree(self.model_dir)

  def fit_on_batch(self, X, y, w):
    """
    Updates existing model with new information.
    """
    raise NotImplementedError(
        "Each model is responsible for its own fit_on_batch method.")

  def predict_on_batch(self, X, **kwargs):
    """
    Makes predictions on given batch of new data.

    Parameters
    ----------
    X: np.ndarray
      Features
    """
    raise NotImplementedError(
        "Each model is responsible for its own predict_on_batch method.")

  def reload(self):
    """
    Reload trained model from disk.
    """
    raise NotImplementedError(
        "Each model is responsible for its own reload method.")

  @staticmethod
  def get_model_filename(model_dir):
    """
    Given model directory, obtain filename for the model itself.
    """
    return os.path.join(model_dir, "model.joblib")

  @staticmethod
  def get_params_filename(model_dir):
    """
    Given model directory, obtain filename for the model itself.
    """
    return os.path.join(model_dir, "model_params.joblib")

  def save(self):
    """Dispatcher function for saving.

    Each subclass is responsible for overriding this method.
    """
    raise NotImplementedError

  def fit(self, dataset, nb_epoch=10, batch_size=50, **kwargs):
    """
    Fits a model on data in a Dataset object.
    """
    # TODO(rbharath/enf): We need a structured way to deal with potential GPU
    #                     memory overflows.
    for epoch in range(nb_epoch):
      log("Starting epoch %s" % str(epoch + 1), self.verbose)
      losses = []
      for (X_batch, y_batch, w_batch,
           ids_batch) in dataset.iterbatches(batch_size):
        losses.append(self.fit_on_batch(X_batch, y_batch, w_batch))
      log("Avg loss for epoch %d: %f" % (epoch + 1, np.array(losses).mean()),
          self.verbose)

  def predict(self, dataset, transformers=[], batch_size=None):
    """
    Uses self to make predictions on provided Dataset object.

    Returns:
      y_pred: numpy ndarray of shape (n_samples,)
    """
    y_preds = []
    n_tasks = self.get_num_tasks()
    ind = 0

    for (X_batch, _, _, ids_batch) in dataset.iterbatches(
        batch_size, deterministic=True):
      n_samples = len(X_batch)
      y_pred_batch = self.predict_on_batch(X_batch)
      # Discard any padded predictions
      y_pred_batch = y_pred_batch[:n_samples]
      #y_pred_batch = np.reshape(y_pred_batch, (n_samples, n_tasks))
      y_pred_batch = undo_transforms(y_pred_batch, transformers)
      y_preds.append(y_pred_batch)
    # y_pred = np.vstack(y_preds)

    # # The iterbatches does padding with zero-weight examples on the last batch.
    # # Remove padded examples.
    # n_samples = len(dataset)
    # y_pred = np.reshape(y_pred, (n_samples, n_tasks))
    # # Special case to handle singletasks.
    # if n_tasks == 1:
    #   y_pred = np.reshape(y_pred, (n_samples,))
    y_pred = np.concatenate(y_preds)
    return y_pred

  def evaluate(self, dataset, metrics, transformers=[], per_task_metrics=False, 
    no_concordance_index=False, plot=False, is_training_set=False, tasks=None, 
    model_name=None, no_r2=False):
    """
    Evaluates the performance of this model on specified dataset.

    Parameters
    ----------
    dataset: dc.data.Dataset
      Dataset object.
    metric: deepchem.metrics.Metric
      Evaluation metric
    transformers: list
      List of deepchem.transformers.Transformer
    per_task_metrics: bool
      If True, return per-task scores.

    Returns
    -------
    dict
      Maps tasks to scores under metric.
    """
    evaluator = Evaluator(self, dataset, transformers, is_training_set=is_training_set, 
      tasks=tasks, model_name=model_name)
    if not per_task_metrics:
      scores = evaluator.compute_model_performance(metrics, 
        no_concordance_index=no_concordance_index, plot=plot, no_r2=no_r2)
      return scores
    else:
      scores, per_task_scores = evaluator.compute_model_performance(
          metrics, per_task_metrics=per_task_metrics, no_r2=no_r2,
          no_concordance_index=no_concordance_index, plot=plot)
      return scores, per_task_scores

  def get_task_type(self):
    """
    Currently models can only be classifiers or regressors.
    """
    raise NotImplementedError

  def get_num_tasks(self):
    """
    Get number of tasks.
    """
    raise NotImplementedError
