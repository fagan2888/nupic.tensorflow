#  Numenta Platform for Intelligent Computing (NuPIC)
#  Copyright (C) 2019, Numenta, Inc.  Unless you have an agreement
#  with Numenta, Inc., for a separate license for this software code, the
#  following terms and conditions apply:
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Affero Public License for more details.
#
#  You should have received a copy of the GNU Affero Public License
#  along with this program.  If not, see http://www.gnu.org/licenses.
#
#  http://numenta.org/licenses/
#

import random

import numpy as np
import tensorflow as tf

from tensorflow.python import keras
from tensorflow.python.eager import context
from tensorflow.python.keras import keras_parameterized
from tensorflow.python.keras import testing_utils
from tensorflow.python.platform import test

from nupic.tensorflow.layers import compute_kwinners

from nupic.tensorflow.constraints import SparseWeights
from nupic.tensorflow.layers import KWinners, KWinners2d


SEED = 18
CUSTOM_OBJECTS = {
    "KWinners": KWinners,
    "KWinners2d": KWinners2d,
    "SparseWeights": SparseWeights,
}


class KWinnersTestBase(object):
    """
    Base module for setting up tests.
    """

    @classmethod
    def setUpClass(cls):
        tf.set_random_seed(SEED)
        np.random.seed(SEED)
        random.seed(SEED)

    def setUp(self):
        super(KWinnersTestBase, self).setUp()

        # Batch size 2
        self.x1 = np.array(
            [[1.0, 1.2, 1.1, 1.3, 1.0, 1.5, 1.0],
             [1.1, 1.0, 1.2, 1.0, 1.3, 1.0, 1.2]],
            dtype=np.float32
        )

        # All equal duty cycle for x.
        self.duty_cycles1 = np.full(shape=(7,), fill_value=1.0 / 3.0, dtype=np.float32)

        # Batch size 2
        self.x2 = np.array(
            [[1.5, 1.0, 1.1, 1.3, 1.0, 1.0],
             [1.1, 1.0, 1.2, 1.6, 1.0, 1.0]],
            dtype=np.float32
        )

        # Unequal duty cycle for x2.
        self.duty_cycles2 = np.array(
            [2, 1, 2, 1, 2, 1],
            dtype=np.float32
        ) / 4

        # Batch size 2, but with negative entries.
        self.x3 = np.array(
            [[1.0, -1.2, 1.2, 1.0, 1.0, 1.0],
             [1.0, 1.2, -1.2, 1.0, 1.0, 1.0]],
            dtype=np.float32
        )

        # Unequal duty cycle for x3.
        self.duty_cycles3 = np.array(
            [0.0, 0.001, 100, 0.0, 0.0, 0.0],
            dtype=np.float32
        )

        # Batch size 1.
        self.x4 = np.array(
            [[1.0, 1.0, 1.2, 1.2, 1.2, 1.2, 1.3, 1.3, 1.3, 1.3]],
            dtype=np.float32
        )

        # All equal duty cycle for x4.
        self.duty_cycles4 = np.ones_like(self.x4) / 10


class KWinnersFowardTest(KWinnersTestBase, keras_parameterized.TestCase):
    """
    Module for testing the forward pass, i.e. the compute_kwinners function.
    """

    def test_one(self):
        """boost strength 0 to 10, k=3, batch size 2"""

        # Setup input.
        x = self.x1
        duty_cycles = self.duty_cycles1

        # Test forward pass through the layer.
        expected = np.zeros(x.shape, dtype=np.float32)
        expected[0, 1] = 1.2
        expected[0, 3] = 1.3
        expected[0, 5] = 1.5
        expected[1, 2] = 1.2
        expected[1, 4] = 1.3
        expected[1, 6] = 1.2

        # Loop over floating point boost strengths.
        for b in np.arange(0.0, 10.0, dtype=np.float32):

            # Build layer with varying boost_strength.
            result = compute_kwinners(x, 3, duty_cycles, boost_strength=0.0)
            self.assertAllEqual(result, expected)

    def test_two(self):
        """
        Unequal duty cycle, boost strength 0 to 10, k = 3, batch size 2.
        """

        # Setup input.
        x = self.x2
        duty_cycles = self.duty_cycles2

        # Test forward with boost strength of 0.
        expected = np.zeros(x.shape, dtype=np.float32)
        expected[0, 0] = 1.5
        expected[0, 2] = 1.1
        expected[0, 3] = 1.3
        expected[1, 0] = 1.1
        expected[1, 2] = 1.2
        expected[1, 3] = 1.6

        result = compute_kwinners(x, 3, duty_cycles, boost_strength=0.0)
        self.assertAllEqual(result, expected)

        # Test forward again with boost strength of 1.
        expected = np.zeros(x.shape, dtype=np.float32)
        expected[0, 0] = 1.5
        expected[0, 1] = 1.0
        expected[0, 3] = 1.3
        expected[1, 1] = 1.0
        expected[1, 3] = 1.6
        expected[1, 5] = 1.0

        result = compute_kwinners(x, 3, duty_cycles, boost_strength=1.0)
        self.assertAllEqual(result, expected)

        # Test forward again with boost strength from 2 to 10. Should give save result
        # given the differing duty cycles.
        expected = np.zeros(x.shape, dtype=np.float32)
        expected[0, 1] = 1.0
        expected[0, 3] = 1.3
        expected[0, 5] = 1.0
        expected[1, 1] = 1.0
        expected[1, 3] = 1.6
        expected[1, 5] = 1.0

        for b in np.arange(2.0, 10.0, dtype=np.float32):

            result = compute_kwinners(x, 3, duty_cycles, boost_strength=b)
            self.assertAllEqual(result, expected)

    def test_three(self):
        """
        Unequal duty cycle, boost factor 0 (and then over a range), k = 3, batch size 2.
        """

        # Setup input.
        x = self.x3
        duty_cycles = self.duty_cycles3

        # Test forward with boost factor of 0.
        expected = np.zeros(x.shape, dtype=np.float32)
        expected[0, 0] = 1.0
        expected[0, 2] = 1.2
        expected[1, 0] = 1.0
        expected[1, 1] = 1.2

        result = compute_kwinners(x, 2, duty_cycles, boost_strength=0.0)
        self.assertAllEqual(result, expected)

        # Test forward again with boost factor from 1 to 10. Should yield the same result
        # as the negative numbers will never be in the top k and the non-one values
        # have very large duty cycles.
        expected = np.zeros(x.shape, dtype=np.float32)
        expected[0, 0] = 1.0
        expected[0, 3] = 1.0
        expected[1, 0] = 1.0
        expected[1, 1] = 1.2

        for b in np.arange(2.0, 10.0, dtype=np.float32):

            result = compute_kwinners(x, 2, duty_cycles, boost_strength=b)
            self.assertAllEqual(result, expected)

    def test_four(self):
        """
        All equal duty cycle, boost factor 0, k = 0,1, and n, batch size 1.
        """

        # Setup input.
        x = self.x4
        duty_cycles = self.duty_cycles4

        # Test forward with boost factor of 1 and k=0.
        expected = np.zeros(x.shape, dtype=np.float32)

        result = compute_kwinners(x, 0, duty_cycles, boost_strength=1.0)
        self.assertAllEqual(result, expected)

        # Test forward with boost factor of 1 and k=1.
        expected[0, 6] = 1.3

        result = compute_kwinners(x, 1, duty_cycles, boost_strength=1.0)
        self.assertAllEqual(result, expected)

        # Test forward with boost factor of 1 and k=1.
        expected = np.copy(x)

        result = compute_kwinners(x, 10, duty_cycles, boost_strength=1.0)
        self.assertAllEqual(result, expected)


class KWinners1DLayerTest(KWinnersTestBase, keras_parameterized.TestCase):
    """
    Module for testing the 1D KWinners layer.
    """

    @keras_parameterized.run_all_keras_modes
    def test_one(self):

        # Set input, output, and layer params.
        x = self.x2
        expected = np.zeros(x.shape, dtype=np.float32)
        expected[0, 0] = 1.5
        expected[0, 2] = 1.1
        expected[0, 3] = 1.3
        expected[1, 0] = 1.1
        expected[1, 2] = 1.2
        expected[1, 3] = 1.6
        kwargs = {
            "percent_on": 0.333,
            "k_inference_factor": 1.5,
            "boost_strength": 1.0,
            "boost_strength_factor": 0.5,
            "duty_cycle_period": 1000,
        }

        # Use testing utils to validate layer functionality.
        with self.cached_session(), keras.utils.custom_object_scope(CUSTOM_OBJECTS):

            testing_utils.layer_test(KWinners,
                                     kwargs=kwargs,
                                     input_data=x,
                                     expected_output=expected,
                                     )

    def test_two(self):

        # Set input, output, and layer params.
        x = self.x2
        expected = np.zeros(x.shape, dtype=np.float32)
        expected[0, 0] = 1.5
        expected[0, 2] = 1.1
        expected[0, 3] = 1.3
        expected[1, 0] = 1.1
        expected[1, 2] = 1.2
        expected[1, 3] = 1.6
        kwargs = {
            "percent_on": 0.333,
            "k_inference_factor": 1.5,
            "boost_strength": 1.0,
            "boost_strength_factor": 0.5,
            "duty_cycle_period": 1000,
        }

        # Test layer output in and out of training mode.
        with context.eager_mode():

            kw = KWinners(**kwargs)
            kw.build(input_shape=x.shape)
            # print(kw.learning_iterations, kw.duty_cycles)
            result = kw(x, training=False)
            self.assertAllEqual(result, expected)
            # print(kw.learning_iterations, kw.duty_cycles)

            result = kw(x, training=False)
            # self.assertAllEqual(result, expected)
            # print(kw.learning_iterations, kw.duty_cycles)

            expected = np.zeros(x.shape, dtype=np.float32)
            expected[0, 0] = 1.5
            expected[0, 3] = 1.3
            expected[1, 2] = 1.2
            expected[1, 3] = 1.6

            kw = KWinners(**kwargs)
            result = kw(x, training=True)
            self.assertAllEqual(result, expected)

            # Test values of updated duty cycle.
            new_duty = np.array([1.0, 0, 1.0, 2.0, 0, 0], dtype=np.float32) / 2.0
            self.assertAllEqual(new_duty, kw.duty_cycles.numpy())

            # Test forward with updated duty cycle.
            expected = np.zeros(x.shape, dtype=np.float32)
            expected[0, 1] = 1.0
            expected[0, 4] = 1.0
            expected[1, 1] = 1.0
            expected[1, 4] = 1.0

            result = kw(x, training=True)
            self.assertAllEqual(result, expected)

    def test_three(self):
        """
        Test a series of calls on the layer in training mode.
        """

        x = self.x2

        expected = np.zeros_like(x)
        expected[0, 0] = 1.5
        expected[0, 4] = 1.0
        expected[1, 2] = 1.2
        expected[1, 3] = 1.6

        kwargs = {
            "percent_on": 0.333,
            "k_inference_factor": 1.5,
            "boost_strength": 1.0,
            "boost_strength_factor": 0.5,
            "duty_cycle_period": 1000,
        }

        with context.eager_mode():

            kw = KWinners(**kwargs)
            kw.build(input_shape=tf.TensorShape(x.shape))

            result = kw(x, training=True)
            result = kw(x, training=True)
            result = kw(x, training=True)
            result = kw(x, training=True)
            result = kw(x, training=True)
            result = kw(x, training=True)
            result = kw(x, training=True)

            self.assertAllEqual(result, expected)


class KWinners2DLayerTest(keras_parameterized.TestCase):
    """
    Module for testing the 1D KWinners layer.
    """

    def setUp(self):

        super().setUp()

        # Batch size 1
        self.x1 = np.ones((1, 3, 2, 2), dtype=np.float32)
        self.x1[0, 0, 1, 0] = 1.1
        self.x1[0, 0, 1, 1] = 1.2
        self.x1[0, 1, 0, 1] = 1.2
        self.x1[0, 2, 1, 0] = 1.3

        # Batch size 2
        self.x2 = np.ones((2, 3, 2, 2), dtype=np.float32)

        self.x2[0, 0, 1, 0] = 1.1
        self.x2[0, 0, 1, 1] = 1.2
        self.x2[0, 1, 0, 1] = 1.2
        self.x2[0, 2, 1, 0] = 1.3

        self.x2[1, 0, 0, 0] = 1.4
        self.x2[1, 1, 0, 0] = 1.5
        self.x2[1, 1, 0, 1] = 1.6
        self.x2[1, 2, 1, 1] = 1.7

    @keras_parameterized.run_all_keras_modes
    def test_one(self):
        """Equal duty cycle, boost strength 0, k=4, batch size 1."""
        x = self.x1
        expected = np.zeros_like(x)
        expected[0, 0, 1, 0] = 1.1
        expected[0, 0, 1, 1] = 1.2
        expected[0, 1, 0, 1] = 1.2
        expected[0, 2, 1, 0] = 1.3

        n = np.prod(x.shape[1:])
        kwargs = {
            "percent_on": 4 / n,
            "k_inference_factor": 1.0,
            "boost_strength": 0.0}
        with self.cached_session(), keras.utils.custom_object_scope(CUSTOM_OBJECTS):
            testing_utils.layer_test(KWinners2d,
                                     kwargs=kwargs,
                                     input_data=x,
                                     expected_output=expected)

    @keras_parameterized.run_all_keras_modes
    def test_two(self):
        """Equal duty cycle, boost strength 0, k=3."""
        x = self.x1
        expected = np.zeros(x.shape)
        expected[0, 0, 1, 1] = 1.2
        expected[0, 1, 0, 1] = 1.2
        expected[0, 2, 1, 0] = 1.3
        n = np.prod(x.shape[1:])
        kwargs = {
            "percent_on": 3 / n,
            "k_inference_factor": 1.0,
            "boost_strength": 0.0}

        with self.cached_session(), keras.utils.custom_object_scope(CUSTOM_OBJECTS):
            testing_utils.layer_test(KWinners2d,
                                     kwargs=kwargs,
                                     input_data=x,
                                     expected_output=expected)

    @keras_parameterized.run_all_keras_modes
    def test_three(self):
        """Equal duty cycle, boost strength=0, k=4, batch size=2."""
        x = self.x2
        expected = np.zeros(x.shape)
        expected[0, 0, 1, 0] = 1.1
        expected[0, 0, 1, 1] = 1.2
        expected[0, 1, 0, 1] = 1.2
        expected[0, 2, 1, 0] = 1.3
        expected[1, 0, 0, 0] = 1.4
        expected[1, 1, 0, 0] = 1.5
        expected[1, 1, 0, 1] = 1.6
        expected[1, 2, 1, 1] = 1.7

        n = np.prod(x.shape[1:])
        kwargs = {
            "percent_on": 4 / n,
            "k_inference_factor": 1.0,
            "boost_strength": 0.0}
        with self.cached_session(), keras.utils.custom_object_scope(CUSTOM_OBJECTS):
            testing_utils.layer_test(KWinners2d,
                                     kwargs=kwargs,
                                     input_data=x,
                                     expected_output=expected)

    @keras_parameterized.run_all_keras_modes
    def test_four(self):
        """Equal duty cycle, boost strength=0, k=3, batch size=2."""
        x = self.x2
        expected = np.zeros(x.shape)
        expected[0, 0, 1, 1] = 1.2
        expected[0, 1, 0, 1] = 1.2
        expected[0, 2, 1, 0] = 1.3
        expected[1, 1, 0, 0] = 1.5
        expected[1, 1, 0, 1] = 1.6
        expected[1, 2, 1, 1] = 1.7

        n = np.prod(x.shape[1:])
        kwargs = {
            "percent_on": 3 / n,
            "k_inference_factor": 1.0,
            "boost_strength": 0.0}
        with self.cached_session(), keras.utils.custom_object_scope(CUSTOM_OBJECTS):
            testing_utils.layer_test(KWinners2d,
                                     kwargs=kwargs,
                                     input_data=x,
                                     expected_output=expected)

    def test_five(self):
        """
        Test a series of calls on the layer in training mode.
        """

        x = self.x2

        expected = np.zeros_like(x)
        expected[0, 0, 1, 0] = 1.1
        expected[0, 0, 1, 1] = 1.2
        expected[0, 2, 1, 0] = 1.3
        expected[1, 0, 0, 0] = 1.4
        expected[1, 1, 0, 1] = 1.6
        expected[1, 2, 1, 1] = 1.7

        kwargs = {
            "percent_on": 0.25,
            "k_inference_factor": 0.5,
            "boost_strength": 1.0,
            "boost_strength_factor": 0.5,
            "duty_cycle_period": 1000,
        }

        with context.eager_mode():

            kw = KWinners2d(**kwargs)
            kw.build(input_shape=tf.TensorShape(x.shape))

            result = kw(x, training=True)
            result = kw(x, training=True)
            result = kw(x, training=True)
            result = kw(x, training=True)
            result = kw(x, training=True)
            result = kw(x, training=True)

            self.assertAllEqual(result, expected)


if __name__ == "__main__":
    test.main()
