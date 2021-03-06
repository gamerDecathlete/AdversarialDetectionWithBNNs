import os
os.environ["MKL_THREADING_LAYER"] = "GNU"

import math

import numpy as np

import sys
sys.path.append('PBP_net/')
import PBP_net
from torchvision import datasets, transforms
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
import glob
import Uncertainty


np.random.seed(1)

# We load the boston housing dataset


# We obtain the features and the targets
train = datasets.MNIST('./data', train=True, transform=transforms.Compose([transforms.ToTensor()]), download=False)
test = datasets.MNIST('./dataTest', train=False, transform=transforms.Compose([transforms.ToTensor()]), download=False)

# We create the train and test sets with 90% and 10% of the data

X_train = train.train_data.view(-1, 28 * 28).numpy()
y_train = train.train_labels.numpy()
#X_test = test.test_data.view(-1, 28 * 28).numpy()
#y_test = test.test_labels.numpy()

print(X_train.shape)
print(y_train.shape)
#print(X_test.shape)
#print(y_test.shape)

# We construct the network with one hidden layer with two-hidden layers
# with 50 neurons in each one and normalizing the training features to have
# zero mean and unit standard deviation in the trainig set.

n_hidden_units = 50
net = PBP_net.load_PBP_net_from_file('pbp_network')
#net = PBP_net.PBP_net(X_train, y_train,
#    [n_hidden_units, n_hidden_units,  n_hidden_units, n_hidden_units, n_hidden_units ], normalize = True, n_epochs = 50)

# We make predictions for the test set
#for i in range(0, 100):
net.save_to_file('pbp_network')

def createProbabilityOfClasses(X_test, samples=10):
    outputs = np.zeros((X_test.shape[0], 10))
    X_test = X_test.data.cpu().numpy()
    for j in range(0, samples):
        net.sample_weights()
        #m, v, v_noise = net.predict(X_test)
        m = net.predict_deterministic(X_test)

        labels = np.rint(m)
        #what is good programming?
        labels[labels > 9.0] = 9 
        labels[labels < 0.0] = 0

        for k, l in enumerate(labels):
            outputs[k,int(l) ] += 1
    outputs = F.softmax(Variable(torch.from_numpy(outputs)), dim=1)
    return outputs


#print(np.count_nonzero(y_test == np.int32(winners)) / float(y_test.shape[0]))

######################################################################################################
#test model
outputs = 10
datasets = {'RegularImages_0.0': [test.test_data, test.test_labels]}

fgsm = glob.glob('fgsm/fgsm_mnist_adv_x_1000_*')
fgsm_labels = torch.from_numpy(np.argmax(np.load('fgsm/fgsm_mnist_adv_y_1000.npy'), axis=1))
for file in fgsm:
    parts = file.split('_')
    key = parts[0].split('/')[0] + '_' + parts[-1].split('.npy')[0]

    datasets[key] = [torch.from_numpy(np.load(file)), fgsm_labels]

jsma = glob.glob('jsma/jsma_mnist_adv_x_10000*')
jsma_labels = torch.from_numpy(np.argmax(np.load('jsma/jsma_mnist_adv_y_10000.npy'), axis=1))
for file in jsma:
    parts = file.split('_')
    key = parts[0].split('/')[0] + '_' + parts[-1].split('.npy')[0]

    datasets[key] = [torch.from_numpy(np.load(file)), jsma_labels]

gaussian = glob.glob('gaussian/mnist_gaussian_adv_x*')
gaussian_labels = torch.from_numpy(np.argmax(np.load('gaussian/mnist_gaussian_adv_y.npy'), axis=1))

for file in gaussian:
    parts = file.split('_')
    key = parts[0].split('/')[0] + '_' + parts[-1].split('.npy')[0]

    datasets[key] = [torch.from_numpy(np.load(file)), jsma_labels]



print(datasets.keys())
print('################################################################################')
accuracies = {}
for key, value in datasets.iteritems():
    print(key)
    parts = key.split('_')
    adversary_type = parts[0]
    epsilon = parts[1]
    data = value
    X, y = data[0].view(-1, 28 * 28), data[1]
    x_data, y_data = Variable(X.float().cuda()), Variable(y.cuda())
    T = 50

    accs = []
    samples = np.zeros((y_data.data.size()[0], T, outputs))
    for i in range(T):
        pred = createProbabilityOfClasses(x_data, samples=20)
        samples[:, i, :] = pred.data.cpu().numpy()
        _, out = torch.max(pred, 1)
        acc = np.count_nonzero(np.squeeze(out.data.cpu().numpy()) == np.int32(y_data.data.cpu().numpy().ravel())) / float(len(y_data.data.cpu().numpy()))
        accs.append(acc)

    variationRatio = []
    mutualInformation = []
    predictiveEntropy = []
    predictions = []

    for i in range(0, len(y_data)):
        entry = samples[i, :, :]
        variationRatio.append(Uncertainty.variation_ratio(entry))
        mutualInformation.append(Uncertainty.mutual_information(entry))
        predictiveEntropy.append(Uncertainty.predictive_entropy(entry))
        predictions.append(np.max(entry.mean(axis=0), axis=0))


    uncertainty={}
    uncertainty['varation_ratio']= np.array(variationRatio)
    uncertainty['predictive_entropy']= np.array(predictiveEntropy)
    uncertainty['mutual_information']= np.array(mutualInformation)
    predictions = np.array(predictions)

    Uncertainty.plot_uncertainty(uncertainty,predictions,adversarial_type=adversary_type,epsilon=float(epsilon), directory='Results_MNIST_PBP')

    accs = np.array(accs)
    print('Accuracy mean: {}, Accuracy std: {}'.format(accs.mean(), accs.std()))
    #accuracies[key] = {'mean': accs.mean(), 'std': accs.std()}
    accuracies[key] = {'mean': accs.mean(), 'std': accs.std(),  \
                       'variationratio': [uncertainty['varation_ratio'].mean(), uncertainty['varation_ratio'].std()], \
                       'predictiveEntropy': [uncertainty['predictive_entropy'].mean(), uncertainty['predictive_entropy'].std()], \
                       'mutualInformation': [uncertainty['mutual_information'].mean(), uncertainty['mutual_information'].std()]}

np.save('PBP_Accuracies_MNIST', accuracies)

