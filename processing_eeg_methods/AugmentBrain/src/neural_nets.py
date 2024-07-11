# File heavily based on https://github.com/CrisSherban/BrainPad
import warnings

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import Model, regularizers
from tensorflow.keras.constraints import max_norm
from tensorflow.keras.layers import (Activation, AveragePooling2D,
                                     BatchNormalization, Conv2D, Dense,
                                     DepthwiseConv2D, Dropout, Flatten, Input,
                                     Lambda, MaxPooling2D, SeparableConv2D,
                                     SpatialDropout2D)
from tensorflow.keras.models import Sequential
from tensorflow.python.keras.layers import Concatenate

stride = 1
CHANNEL_AXIS = 1


def res_net(nb_classes):
    # ResNet implementation
    warnings.warn(
        "Shape mismatch between this res_net implementation data", DeprecationWarning
    )

    def res_layer(x, filters, pooling=False, dropout=0.0):
        temp = x
        temp = Conv2D(filters, (3, 3), strides=stride, padding="same")(temp)
        temp = BatchNormalization(axis=CHANNEL_AXIS)(temp)
        temp = Activation("relu")(temp)
        temp = Conv2D(filters, (3, 3), strides=stride, padding="same")(temp)

        x = tf.keras.layers.add(
            [temp, Conv2D(filters, (3, 3), strides=stride, padding="same")(x)]
        )
        if pooling:
            x = MaxPooling2D((2, 2))(x)
        if dropout != 0.0:
            x = Dropout(dropout)(x)
        x = BatchNormalization(axis=CHANNEL_AXIS)(x)
        x = Activation("relu")(x)
        return x

    inp = tf.keras.Input(shape=(8, 90, 1))
    x = Conv2D(16, (3, 3), strides=stride, padding="same")(inp)
    x = BatchNormalization(axis=CHANNEL_AXIS)(x)
    x = Activation("relu")(x)
    x = res_layer(x, 32, dropout=0.2)
    x = res_layer(x, 32, dropout=0.3)
    x = res_layer(x, 32, dropout=0.4, pooling=True)
    x = res_layer(x, 64, dropout=0.2)
    x = res_layer(x, 64, dropout=0.2, pooling=True)
    x = res_layer(x, 256, dropout=0.4)
    x = Flatten()(x)
    x = Dropout(0.4)(x)
    x = Dense(4096, activation="relu")(x)
    x = Dropout(0.23)(x)
    x = Dense(nb_classes, activation="softmax")(x)

    model = tf.keras.Model(inp, x, name="Resnet")
    return model


def cris_net(input_shape, nb_classes):
    # simple network
    # inspiration from:
    # https://iopscience.iop.org/article/10.1088/1741-2552/ab0ab5/meta

    model = Sequential(
        [
            Conv2D(
                filters=10,
                kernel_size=(1, 20),
                activation="tanh",
                padding="same",
                input_shape=input_shape,
            ),
            BatchNormalization(),
            Conv2D(
                filters=1,
                kernel_size=(5, 1),
                activation="tanh",
                kernel_regularizer=regularizers.l2(1e-6),
                padding="same",
            ),
            BatchNormalization(),
            AveragePooling2D(pool_size=(2, 1), strides=1),
            Dropout(0.3),
            Flatten(),
            # Dense(4, activation="elu", kernel_regularizer=regularizers.l2(1e-6)),
            Dense(nb_classes, activation="softmax"),
        ],
        name="cris_net",
    )

    return model


def TA_CSPNN(
    nb_classes, Channels=8, Timesamples=250, dropOut=0.25, timeKernelLen=50, Ft=11, Fs=6
):
    """
    Temporally Adaptive Common Spatial Patterns with Deep Convolutional Neural Networks (TA-CSPNN)
    v1.0.1
    MIT License
    Copyright (c) 2019 Mahta Mousavi
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation physionet_dataset (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
    """

    # full credits to: https://github.com/mahtamsv/TA-CSPNN/blob/master/TA_CSPNN.py
    #                  https://ieeexplore.ieee.org/document/8857423
    # input (trials, 1, number of channels, number of time samples)

    # if you want channels first notation:
    # keras.backend.set_image_data_format('channels_first')

    model = Sequential(name="TA_CSPNN")
    model.add(
        Conv2D(
            Ft,
            (1, timeKernelLen),
            padding="same",
            input_shape=(Channels, Timesamples, 1),
            use_bias=False,
        )
    )
    model.add(BatchNormalization(axis=1))
    # Grid searching shows better results with the added tanh activation
    # but the networks has more troubles generalizing
    # model.add(Activation(activation="tanh"))

    model.add(
        DepthwiseConv2D(
            (Channels, 1),
            use_bias=False,
            depth_multiplier=Fs,
            depthwise_constraint=max_norm(1.0),
        )
    )
    model.add(BatchNormalization(axis=1))
    model.add(Lambda(lambda x: x**2))
    model.add(AveragePooling2D((1, Timesamples)))

    model.add(Dropout(dropOut))
    model.add(Flatten())
    model.add(Dense(nb_classes, activation="softmax"))

    return model


def EEGNet(
    nb_classes,
    Chans=8,
    Samples=250,
    dropoutRate=0.5,
    kernLength=125,
    F1=7,
    D=2,
    F2=7,
    norm_rate=0.25,
    dropoutType="Dropout",
):
    """Keras Implementation of EEGNet
    http://iopscience.iop.org/article/10.1088/1741-2552/aace8c/meta
    Note that this implements the newest version of EEGNet and NOT the earlier
    version (version v1 and v2 on arxiv). We strongly recommend using this
    architecture as it performs much better and has nicer properties than
    our earlier version. For example:

        1. Depthwise Convolutions to learn spatial filters within a
        temporal convolution. The use of the depth_multiplier option maps
        exactly to the number of spatial filters learned within a temporal
        filter. This matches the setup of algorithms like FBCSP which learn
        spatial filters within each filter in a filter-bank. This also limits
        the number of free parameters to fit when compared to a fully-connected
        convolution.

        2. Separable Convolutions to learn how to optimally combine spatial
        filters across temporal bands. Separable Convolutions are Depthwise
        Convolutions followed by (1x1) Pointwise Convolutions.


    While the original paper used Dropout, we found that SpatialDropout2D
    sometimes produced slightly better results for classification of ERP
    signals. However, SpatialDropout2D significantly reduced performance
    on the Oscillatory dataset (SMR, BCI-IV Dataset 2A). We recommend using
    the default Dropout in most cases.

    Assumes the input signal is sampled at 128Hz. If you want to use this model
    for any other sampling rate you will need to modify the lengths of temporal
    kernels and average pooling size in blocks 1 and 2 as needed (double the
    kernel lengths for double the sampling rate, etc). Note that we haven't
    tested the model performance with this rule so this may not work well.

    The model with default parameters gives the EEGNet-8,2 model as discussed
    in the paper. This model should do pretty well in general, although it is
        advised to do some model searching to get optimal performance on your
        particular dataset.
    We set F2 = F1 * D (number of input filters = number of output filters) for
    the SeparableConv2D layer. We haven't extensively tested other values of this
    parameter (say, F2 < F1 * D for compressed learning, and F2 > F1 * D for
    overcomplete). We believe the main parameters to focus on are F1 and D.
    Inputs:

      nb_classes      : int, number of classes to classify
      Chans, Samples  : number of channels and time points in the EEG data
      dropoutRate     : dropout fraction
      kernLength      : length of temporal convolution in first layer. We found
                        that setting this to be half the sampling rate worked
                        well in practice. For the SMR dataset in particular
                        since the data was high-passed at 4Hz we used a kernel
                        length of 32.
      F1, F2          : number of temporal filters (F1) and number of pointwise
                        filters (F2) to learn. Default: F1 = 8, F2 = F1 * D.
      D               : number of spatial filters to learn within each temporal
                        convolution. Default: D = 2
      dropoutType     : Either SpatialDropout2D or Dropout, passed as a string.
    """

    if dropoutType == "SpatialDropout2D":
        dropoutType = SpatialDropout2D
    elif dropoutType == "Dropout":
        dropoutType = Dropout
    else:
        raise ValueError(
            "dropoutType must be one of SpatialDropout2D "
            "or Dropout, passed as a string."
        )

    input1 = Input(shape=(Chans, Samples, 1))

    ##################################################################
    block1 = Conv2D(
        F1,
        (1, kernLength),
        padding="same",
        input_shape=(Chans, Samples, 1),
        use_bias=False,
    )(input1)
    block1 = BatchNormalization()(block1)
    block1 = DepthwiseConv2D(
        (Chans, 1),
        use_bias=False,
        depth_multiplier=D,
        depthwise_constraint=max_norm(1.0),
    )(block1)
    block1 = BatchNormalization()(block1)
    block1 = Activation("elu")(block1)
    block1 = AveragePooling2D((1, 4))(block1)
    block1 = dropoutType(dropoutRate)(block1)

    block2 = SeparableConv2D(F2, (1, 16), use_bias=False, padding="same")(block1)
    block2 = BatchNormalization()(block2)
    block2 = Activation("elu")(block2)
    block2 = AveragePooling2D((1, 8))(block2)
    block2 = dropoutType(dropoutRate)(block2)

    flatten = Flatten(name="flatten")(block2)

    dense = Dense(nb_classes, name="dense", kernel_constraint=max_norm(norm_rate))(
        flatten
    )
    softmax = Activation("softmax", name="softmax")(dense)

    return Model(inputs=input1, outputs=softmax, name="EEGNet")


def recurrent_net(nb_classes=3):
    model = keras.Sequential(name="recurrent_net")
    model.add(keras.layers.Input(batch_input_shape=(None, None, 8)))
    model.add(keras.layers.GRU(16, return_sequences=True))
    model.add(keras.layers.GRU(32))
    model.add(keras.layers.Dense(32, activation="elu", kernel_initializer="he_normal"))
    model.add(keras.layers.BatchNormalization())
    model.add(keras.layers.Dense(nb_classes, activation="softmax"))

    return model


def CP_MixedNet(nb_classes, Chans=8, Samples=250, dropoutRate=0.25, F1=12, D=2, F2=24):
    """
    Please refer to https://www.researchgate.net/publication/332953926_A_Channel-Projection_Mixed-Scale_Convolutional_Neural_Network_for_Motor_Imagery_EEG_Decoding
    """
    input = Input(shape=(Chans, Samples, 1))
    # reshaped_input = Reshape(target_shape=(1, Samples, Chans))(input)
    # SP_output = Conv2D(Chans, 1, padding='same')(reshaped_input)
    # SP_output = BatchNormalization(axis=1)(SP_output)
    # SP_output = Activation('elu')(SP_output)
    # SP_output = Dropout(rate=dropoutRate)(SP_output)

    # SP_output = Reshape(target_shape=(Chans, Samples, 1))(SP_output)
    SP_output = Conv2D(F1, kernel_size=(1, 11), padding="same")(input)
    SP_output = BatchNormalization(axis=1)(SP_output)
    SP_output = Activation("elu")(SP_output)
    SP_output = Dropout(rate=dropoutRate)(SP_output)

    SP_output = DepthwiseConv2D((Chans, 1), depth_multiplier=D)(SP_output)
    SP_output = BatchNormalization(axis=1)(SP_output)
    SP_output = Activation("elu")(SP_output)
    SP_output = MaxPooling2D((1, 3))(SP_output)

    # MS-branch1
    MS_branch1 = Conv2D(F2, 1, padding="same")(SP_output)
    MS_branch1 = BatchNormalization(axis=1)(MS_branch1)
    MS_branch1 = Activation("elu")(MS_branch1)
    MS_branch1 = Dropout(rate=dropoutRate)(MS_branch1)

    MS_branch1 = SeparableConv2D(F2, (1, 11), padding="same")(MS_branch1)
    MS_branch1 = BatchNormalization(axis=1)(MS_branch1)
    MS_branch1 = Activation("elu")(MS_branch1)

    # MS-branch2
    MS_branch2 = Conv2D(F2, 1, padding="same")(SP_output)
    MS_branch2 = BatchNormalization(axis=1)(MS_branch2)
    MS_branch2 = Activation("elu")(MS_branch2)
    MS_branch2 = Dropout(rate=dropoutRate)(MS_branch2)

    MS_branch2 = SeparableConv2D(F2, (1, 11), dilation_rate=(1, 2), padding="same")(
        MS_branch2
    )
    MS_branch2 = BatchNormalization(axis=1)(MS_branch2)
    MS_branch2 = Activation("elu")(MS_branch2)

    MS_output = Concatenate()([SP_output, MS_branch1, MS_branch2])
    MS_output = MaxPooling2D((1, 3))(MS_output)

    CB_output = Conv2D(F2, (1, 11))(MS_output)
    CB_output = BatchNormalization(axis=1)(CB_output)
    CB_output = Activation("elu")(CB_output)
    CB_output = MaxPooling2D((1, 3))(CB_output)

    CB_output = Flatten()(CB_output)
    CB_output = BatchNormalization()(CB_output)
    CB_output = Dense(nb_classes, name="dense")(CB_output)
    CB_output = Activation("softmax", name="softmax")(CB_output)

    return Model(inputs=input, outputs=CB_output, name="CP_MixedNet")
