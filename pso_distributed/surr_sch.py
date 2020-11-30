#........................................#
"""
This implementtion also involves the sampled weights in a parameter vector 
for surrogate training for the case of bigger problems like Bank problem,
surrogate_topology to be used in this case =4.

"""
#........................................#
# !/usr/bin/python
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
from numpy import linalg as LA
from scipy.linalg import sqrtm
import scipy.stats
from scipy.stats import skew,kurtosis
np.set_printoptions(suppress=True)
import random
from random import seed
import time
import math
import shutil
import multiprocessing 
import gc
from pyDOE import *
import copy    # array-copying convenience
import sys     # max float
import io
import tensorflow as tf
from keras.models import Sequential
from keras.layers import Activation, Dense, Dropout
from keras.objectives import MSE, MAE
from keras.callbacks import EarlyStopping
from keras.models import model_from_json
from keras.models import load_model
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import warnings 
warnings.filterwarnings("ignore", category=DeprecationWarning)
np.seterr(divide='ignore', invalid='ignore')
# -----------------------------------

# using https://github.com/sydney-machine-learning/canonical_neuroevolution

## import the class for G3PCX from g3-pcx.py
#sys.path.append(".")
#from g3-pcx import neuroevolution_G3PCX as G3PCX
#.....................................
class neuralnetwork:

    def __init__(self, Topo, Train, Test, learn_rate):
        self.Top = Topo  # NN topology [input, hidden, output]
        self.TrainData = Train
        self.TestData = Test
        self.lrate = learn_rate
        self.W1 = np.random.randn(self.Top[0], self.Top[1]) / np.sqrt(self.Top[0])
        self.B1 = np.random.randn(1, self.Top[1]) / np.sqrt(self.Top[1])  # bias first layer
        self.W2 = np.random.randn(self.Top[1], self.Top[2]) / np.sqrt(self.Top[1])
        self.B2 = np.random.randn(1, self.Top[2]) / np.sqrt(self.Top[1])  # bias second layer
        self.hidout = np.zeros((1, self.Top[1]))  # output of first hidden layer
        self.out = np.zeros((1, self.Top[2]))  # output last layer
        self.pred_class = 0
 

    def sigmoid(self, x):
        x = np.float128(x)#to avoid overflow
        #return .5 * (1 + np.tanh(.5 * x))
        return 1 / (1 + np.exp(-x))

    def sampleEr(self, actualout):
        error = np.subtract(self.out, actualout)
        sqerror = np.sum(np.square(error)) / self.Top[2]
        return sqerror

    def ForwardPass(self, X):
        z1 = X.dot(self.W1) - self.B1
        self.hidout = self.sigmoid(z1)  # output of first hidden layer
        z2 = self.hidout.dot(self.W2) - self.B2
        self.out = self.sigmoid(z2)  # output second hidden layer
        #z2 = np.float128(z2)
        #self.out = np.exp(z2)/np.sum(np.exp(z2)) #softmax
        self.pred_class = np.argmax(self.out)


        #print(self.pred_class, self.out, '  ---------------- out ')

    '''def BackwardPass(self, Input, desired):
        out_delta = (desired - self.out).dot(self.out.dot(1 - self.out))
        hid_delta = out_delta.dot(self.W2.T) * (self.hidout * (1 - self.hidout))
        # print(self.B2.shape)
        self.W2 += (self.hidout.T.reshape(self.Top[1],1).dot(out_delta) * self.lrate)
        self.B2 += (-1 * self.lrate * out_delta)
        self.W1 += (Input.T.reshape(self.Top[0],1).dot(hid_delta) * self.lrate)
        self.B1 += (-1 * self.lrate * hid_delta)'''




    def BackwardPass(self, Input, desired): # since data outputs and number of output neuons have different orgnisation

        #print(Input, desired, '  ** ss')
        #onehot = np.zeros((desired.size, self.Top[2]))


        #print(onehot, ' bp -')


        #onehot[np.arange(desired.size),int(desired)] = 1

        #print(onehot, ' bp')
        #desired = onehot
        out_delta = (desired - self.out)*(self.out*(1 - self.out))
        hid_delta = np.dot(out_delta,self.W2.T) * (self.hidout * (1 - self.hidout))
        self.W2 += np.dot(self.hidout.T,(out_delta * self.lrate))
        self.B2 += (-1 * self.lrate * out_delta)
        Input = Input.reshape(1,self.Top[0])
        self.W1 += np.dot(Input.T,(hid_delta * self.lrate))
        self.B1 += (-1 * self.lrate * hid_delta)


    def decode(self, w):
        w_layer1size = self.Top[0] * self.Top[1]
        w_layer2size = self.Top[1] * self.Top[2]

        w_layer1 = w[0:w_layer1size]
        self.W1 = np.reshape(w_layer1, (self.Top[0], self.Top[1]))

        w_layer2 = w[w_layer1size:w_layer1size + w_layer2size]
        self.W2 = np.reshape(w_layer2, (self.Top[1], self.Top[2]))
        self.B1 = w[w_layer1size + w_layer2size:w_layer1size + w_layer2size + self.Top[1]].reshape(1,self.Top[1])
        self.B2 = w[w_layer1size + w_layer2size + self.Top[1]:w_layer1size + w_layer2size + self.Top[1] + self.Top[2]].reshape(1,self.Top[2])



    def encode(self):
        w1 = self.W1.ravel()
        w1 = w1.reshape(1,w1.shape[0])
        w2 = self.W2.ravel()
        w2 = w2.reshape(1,w2.shape[0])
        w = np.concatenate([w1.T, w2.T, self.B1.T, self.B2.T])
        w = w.reshape(-1)
        return w

    def softmax(self):
        prob = np.exp(self.out)/np.sum(np.exp(self.out))
        return prob



    def langevin_gradient(self, data, w, depth):  # BP with SGD (Stocastic BP)

        self.decode(w)  # method to decode w into W1, W2, B1, B2.
        size = data.shape[0]

        #Input = np.zeros((1, self.Top[0]))  # temp hold input
        #Desired = np.zeros((1, self.Top[2]))

        fx = np.zeros(size)

        for i in range(0, depth):
            for i in range(0, size):
                pat = i
                Input = data[pat, 0:self.Top[0]]
                Desired = data[pat, self.Top[0]:]
                #print(Desired, i,  '  desired ')
                self.ForwardPass(Input)
                self.BackwardPass(Input, Desired)
        w_updated = self.encode()

        return  w_updated

    def evaluate_proposal(self, data, w ):  # BP with SGD (Stocastic BP)

        self.decode(w)  # method to decode w into W1, W2, B1, B2.
        size = data.shape[0]

        Input = np.zeros((1, self.Top[0]))  # temp hold input
        Desired = np.zeros((1, self.Top[2]))
        #print(Desired, ' desired')
        fx = np.zeros(size)
        prob = np.zeros((size,self.Top[2]))

        for i in range(0, size):  # to see what fx is produced by your current weight update
            Input = data[i, 0:self.Top[0]]
            self.ForwardPass(Input)
            fx[i] = self.pred_class
            prob[i] = self.softmax()

        ## print(fx, 'fx')
        ## print(prob, 'prob' )

        return fx, prob




class evaluate_neuralnetwork(object):  # class for fitness func 
    def __init__(self,  netw, traindata, testdata):


        learn_rate = 0.1 # in case you wish to use gradients to help evolution
        self.neural_net = neuralnetwork(netw, traindata, testdata, learn_rate)  # FNN model, but can be extended to RNN model
        self.traindata = traindata
        self.testdata = testdata
        self.topology = netw
  


    def rmse(self, pred, actual):
        return np.sqrt(((pred-actual)**2).mean())

    def accuracy(self,pred,actual ):
        count = 0
        for i in range(pred.shape[0]):
            if pred[i] == actual[i]:
                count+=1
        return 100*(count/pred.shape[0])

    def classification_perf(self, x, type_data):

        if type_data == 'train':
            data = self.traindata
        else:
            data = self.testdata

        y = data[:, self.topology[0]]
        fx, prob = self.neural_net.evaluate_proposal(data,x)
        fit= self.rmse(fx,y) 
        acc = self.accuracy(fx,y) 

        return acc, fit

        
    def fit_func(self, x):    #  function  (can be any other function, model or diff neural network models (FNN or RNN ))
          
        y = self.traindata[:, self.topology[0]]
        fx, prob = self.neural_net.evaluate_proposal(self.traindata,x)
        #fit= self.rmse(fx,y) 
        #return fit
        acc = self.accuracy(fx,y) 
        return 1/(acc+1)#fit # note we will maximize fitness, hence minimize error



    def neuro_gradient(self, data, w, depth):  # BP with SGD (Stocastic BP)

        gradients = self.neural_net.langevin_gradient(data, w, depth)

        return gradients

##########################################
# SURROGATE CLASS
class surrogate: #General Class for surrogate models for predicting likelihood(here the fitness) given the weights

    def __init__(self, model, X, Y, min_X, max_X, min_Y , max_Y, path, save_surrogate_data, model_topology):

        self.path = path + '/surrogate'
        indices = np.where(Y==np.inf)[0]
        X = np.delete(X, indices, axis=0)
        Y = np.delete(Y, indices, axis=0)
        self.model_signature = 0.0
        self.X = X
        self.Y = Y
        self.min_Y = min_Y
        self.max_Y = max_Y
        self.min_X = min_X
        self.max_X = max_X

        self.model_topology = model_topology

        self.save_surrogate_data =  save_surrogate_data

        if model=="gp":
            self.model_id = 1
        elif model == "nn":
            self.model_id = 2
        elif model == "krnn": # keras nn
            self.model_id = 3
            self.krnn = Sequential()
        else:
            print("Invalid Model!")
    # This function is ignored
    def create_model(self):
        krnn = Sequential()

        if self.model_topology == 1:
            krnn.add(Dense(64, input_dim=self.X.shape[1], kernel_initializer='uniform', activation ='relu')) #64
            krnn.add(Dense(16, kernel_initializer='uniform', activation='relu'))  #16

        if self.model_topology == 2:
            krnn.add(Dense(120, input_dim=self.X.shape[1], kernel_initializer='uniform', activation ='relu')) #64
            krnn.add(Dense(40, kernel_initializer='uniform', activation='relu'))  #16

        if self.model_topology == 3:
            krnn.add(Dense(200, input_dim=self.X.shape[1], kernel_initializer='uniform', activation ='relu')) #64
            krnn.add(Dense(50, kernel_initializer='uniform', activation='relu'))  #16
        #....................................#
        # The following topology if basically for training the sampled datasets with 3 moments as features.
        if self.model_topology == 4:
            krnn.add(Dense(64, input_dim=self.X.shape[1], kernel_initializer='uniform', activation ='relu')) 
            #krnn.add(Dense(120, input_dim=self.X.shape[1], kernel_initializer='uniform', activation ='relu')) 
            krnn.add(Dropout(0.2)) #This dropout layer can be used to reduce overfitting in case of small amount of dataset.
        #....................................#
        krnn.add(Dense(1, kernel_initializer ='uniform', activation='sigmoid'))
        return krnn

    def train(self, model_signature):
        #X_train, X_test, y_train, y_test = train_test_split(self.X, self.Y, test_size=0.10, random_state=42)

        X_train = self.X
        X_test = self.X
        y_train = self.Y
        y_test =  self.Y #train_test_split(self.X, self.Y, test_size=0.10, random_state=42)

        self.model_signature = model_signature


        if self.model_id is 3:
            if self.model_signature==1.0:
                self.krnn = self.create_model()
            else:
                while True:
                    try:
                        # You can see two options to initialize model now. If you uncomment the first line then the model id loaded at every time with stored weights. On the other hand if you uncomment the second line a new model will be created every time without the knowledge from previous training. This is basically the third scheme we talked about for surrogate experiments.
                        # To implement the second scheme you need to combine the data from each training.

                        self.krnn = load_model(self.path+'/model_krnn_%s_.h5'%(model_signature-1))
                        #self.krnn = self.create_model()
                        break
                    except EnvironmentError as e:
                        # pass
                        # # print(e.errno)
                        # time.sleep(1)
                        print ('ERROR in loading latest surrogate model, loading previous one in TRAIN')

            early_stopping = EarlyStopping(monitor='val_loss', patience=5)
            self.krnn.compile(loss='mse', optimizer='adam', metrics=['mse'])
            train_log = self.krnn.fit(X_train, y_train.ravel(), batch_size=50, epochs=20, validation_split=0.1, verbose=0, callbacks=[early_stopping])

            scores = self.krnn.evaluate(X_test, y_test.ravel(), verbose = 0)
            # print("%s: %.5f" % (self.krnn.metrics_names[1], scores[1]))

            self.krnn.save(self.path+'/model_krnn_%s_.h5' %self.model_signature)
            # print("Saved model to disk  ", self.model_signature)
 

            results = np.array([round(scores[1] , 4)])

            plt.plot(train_log.history["loss"], label="loss")
            #plt.plot(train_log.history["val_loss"], label="val_loss")
            plt.savefig(self.path+'/%s_0.png'%(self.model_signature))
            plt.clf()

            with open(('%s/train_metrics.txt' % (self.path)),'ab') as outfile:
                np.savetxt(outfile, results)

            if self.save_surrogate_data is True:
                with open(('%s/learnsurrogate_data/X_train.csv' % (self.path)),'ab') as outfile:
                    np.savetxt(outfile, X_train)
                with open(('%s/learnsurrogate_data/Y_train.csv' % (self.path)),'ab') as outfile:
                    np.savetxt(outfile, y_train)
                with open(('%s/learnsurrogate_data/X_test.csv' % (self.path)),'ab') as outfile:
                    np.savetxt(outfile, X_test)
                with open(('%s/learnsurrogate_data/Y_test.csv' % (self.path)),'ab') as outfile:
                    np.savetxt(outfile, y_test)

    def predict(self, X_load, initialized):


        if self.model_id == 3:

            if initialized == False:
                model_sign = np.loadtxt(self.path+'/model_signature.txt')
                self.model_signature = model_sign
                while True:
                    try:
                        self.krnn = load_model(self.path+'/model_krnn_%s_.h5'%self.model_signature)
                        # # print (' Tried to load file : ', self.path+'/model_krnn_%s_.h5'%self.model_signature)
                        break
                    except EnvironmentError as e:
                        print(e)
                        # pass

                self.krnn.compile(loss='mse', optimizer='rmsprop', metrics=['mse'])
                krnn_prediction =-1.0
                prediction = -1.0

            else:
                krnn_prediction = self.krnn.predict(X_load)[0]
                ## Not needed in our case
                prediction = krnn_prediction*(self.max_Y[0,0]-self.min_Y[0,0]) + self.min_Y[0,0]

            return krnn_prediction , prediction
##########################################
class particle(evaluate_neuralnetwork):
    def __init__(self,  dim,  maxx, minx, netw, traindata, testdata, id_island):
        evaluate_neuralnetwork.__init__( self, netw, traindata, testdata) # inherits neuroevolution class definition and methods
        """
        #Latin Hypercube sampling
        np_pos = lhs(dim, samples=1)
        np_vel = lhs(dim, samples=1)
        np_pos = np_pos.reshape((dim,))
        np_vel = np_vel.reshape((dim,))
        """
        #r_pos = np.asarray(random.sample(range(1, dim+1), dim) )/ (dim+1) #to force using random without np and convert to np (to avoid multiprocessing random seed issue)
        
        np_pos = np.random.rand(dim)#/2 + r_pos/2
        np_vel = np.random.rand(dim)#/2 + r_pos/2
        

        self.position = ((maxx - minx) * np_pos  + minx) # using random.rand() rather than np.random.rand() to avoid multiprocesssing random issues
        self.velocity = ((maxx - minx) * np_vel  + minx)


        self.error =  self.fit_func(self.position) # curr error
        self.best_part_pos =  self.position.copy()
        self.best_part_err = self.error # best error 



class neuroevolution(evaluate_neuralnetwork, multiprocessing.Process):  # PSO http://www.scholarpedia.org/article/Particle_swarm_optimization
    def __init__(self, pop_size,lg_prob,dimen, max_evals,  max_limits, min_limits, netw, traindata, testdata, parameter_queue, wait_chain, event, island_id, swap_interval,surrogate_parameter_queues,surrogate_start,surrogate_resume,surrogate_interval,surrogate_prob,save_surrogatedata,use_surrogate,compare_surrogate,surrogate_topology,path):
        
        multiprocessing.Process.__init__(self) # set up multiprocessing class

        evaluate_neuralnetwork.__init__( self, netw, traindata, testdata) # sepossiesiont up - inherits neuroevolution class definition and methods
        #multiprocessing Variables
        self.parameter_queue = parameter_queue
        self.signal_main = wait_chain
        self.event =  event
        self.island_id = island_id
        self.swap_interval = swap_interval
        #Surrogate Variables
        self.surrogate_parameter_queue = surrogate_parameter_queues
        self.surrogate_start = surrogate_start
        self.surrogate_resume = surrogate_resume
        self.surrogate_interval = surrogate_interval
        self.surrogate_prob = surrogate_prob
        self.save_surrogate_data = save_surrogatedata
        self.use_surrogate = use_surrogate
        #self.compare_surrogate = compare_surrogate
        self.compare_surrogate = compare_surrogate
        self.surrogate_topology = surrogate_topology
        # PSO Variables
        self.dim = dimen
        self.num_param = dimen
        self.n = pop_size
        self.minx = min_limits
        self.maxx = max_limits
        self.max_evals = max_evals
        self.minY = np.zeros((1,1))
        self.maxY = np.ones((1,1)) 
        self.EPSILON = 1e-40
        self.lg_prob = lg_prob
        # Network Variables
        self.netw = netw
        self.traindata = traindata
        self.testdata = testdata
        self.path = path
        self.folder = path
        #Plotting variable
        self.plots = []
 
    def sort_swarm(self,swarm_list):
        for i in range(self.n -1):
            for j in range(0,self.n-1-i):
                if(swarm_list[j+1].best_part_err < swarm_list[j].best_part_err):
                    #swap the sample var
                    temp_var = swarm_list[j+1]
                    swarm_list[j+1] = swarm_list[j]
                    swarm_list[j] = temp_var 
        return swarm_list


    def run(self): # this is executed without even calling - due to multi-processing
        netw = self.topology
        y_test = self.testdata[:,netw[0]]
        y_train = self.traindata[:,netw[0]]
        fitness_list = np.zeros((self.max_evals,1))
        surrogate_list = np.zeros((self.max_evals ,1))
        surrogate_model = None 
        surrogate_counter = 0
        trainset_empty = True
        is_true_fit = True
        surg_fit_list = [np.zeros(((int)(self.max_evals/self.n) + 1,3)) for k in range(self.n)]
        index_list = [0 for k in range(self.n)]
        surr_train_set = np.zeros((1000, self.num_param+1))
        local_model_signature = 0.0
        self.surrogate_init = 0.0
        #PSO initialization starts
        np.random.seed(int(self.island_id) )
        swarm = [particle(self.dim, self.minx, self.maxx,  self.netw, self.traindata, self.testdata, self.island_id) for i in range(self.n)] 
     
        best_swarm_pos = [0.0 for i in range(self.dim)] # not necess.
        best_swarm_err = sys.float_info.max # swarm best
    
        for i in range(self.n): # check each particle
            if swarm[i].error < best_swarm_err:
                best_swarm_err = swarm[i].error
                best_swarm_pos = copy.copy(swarm[i].position) 
            
        epoch = 0
        evals = 0
        w = 0.729    # inertia
        #c1 = 1.49445 # cognitive (particle)
        #c2 = 1.49445 # social (swarm)
        c1 = 1.4
        c2 = 1.4
        gradient_prob = self.lg_prob
        use_gradients = True
        
        #clear the event for the islands
        self.event.clear()
        count_real = 0
        while evals < (self.max_evals ):
            #count_real = 0
            recalc = 0
            for i in range(self.n): # process each particle 
                #r_pos = np.asarray(random.sample(range(1, self.dim+1), self.dim) )/ (self.dim+1) #to force using random without np and convert to np (to avoid multiprocessing random seed issue)
                r1 = np.random.rand(self.dim)#/2 + r_pos/2
                r2 = np.random.rand(self.dim)

                swarm[i].velocity = ( (w * swarm[i].velocity) + (c1 * r1 * (swarm[i].best_part_pos - swarm[i].position)) +  (c2 * r2 * (best_swarm_pos - swarm[i].position)) )  
                
                swarm[i].position += swarm[i].velocity

                u = random.uniform(0, 1)
                #depth = random.randint(1, 5)# num of epochs for gradients by backprop
                depth = 1
                swarm[i].position += np.random.normal(0.0,2,self.num_param)
                if u < gradient_prob and use_gradients == True: 

                    swarm[i].position = self.neuro_gradient(self.traindata, swarm[i].position.copy(), depth)  

                for k in range(self.dim): 
                    if swarm[i].position[k] < self.minx[k]:
                        swarm[i].position[k] = self.minx[k]
                    elif swarm[i].position[k] > self.maxx[k]:
                        swarm[i].position[k] = self.maxx[k]    
                    
                #....................................................#
                """
                In this segment of code we try to initialize/predict using the surrogate model. 

                """    
                # creating (X,Y) pair for the surrogate training
                surrogate_X = best_swarm_pos
                best_surr_fit = best_swarm_err
                surrogate_Y = np.array([best_surr_fit])
                # proposed parameters after the evaluation
                w_proposal = swarm[i].position
                #........................................#
                # This part is for the case of sampled surrogate training.  
                if self.surrogate_topology is 4:
                    partitions = 10
                    param_vec = np.array(w_proposal)
                    new_param_vec = []
                    mean_list = []
                    std_list = []
                    skw_list = []
                    krt_list = []
                    chunks = np.array_split(param_vec , partitions)
                    for chunk in chunks:
                        mu = np.mean(chunk)   #Mean
                        std = np.std(chunk)   #Standard-Deviation 
                        skw = skew(chunk)     #skewness
                        krt = kurtosis(chunk)    #Kurtosis
                        mean_list.append(mu)
                        std_list.append(std)
                        skw_list.append(skw)
                        krt_list.append(krt)

                    new_param_vec.extend(mean_list)
                    new_param_vec.extend(std_list)
                    new_param_vec.extend(skw_list)
                    new_param_vec.extend(krt_list) 
                    maxm = max(new_param_vec)
                    minm = min(new_param_vec)   
                    n_param_list = [(i-minm)/(maxm - minm) for i in new_param_vec]
                    w_proposal = np.array(n_param_list)
                #.............................................#
                else:
                    w_proposal = (w_proposal-min(w_proposal))/(max(w_proposal)-min(w_proposal))
                

                #print(w_proposal)
                #if trainset_empty == True:
                #surr_train_set = np.zeros((1, self.num_param+1))
                ku = random.uniform(0,1)
                self.surrogate_prob = 0.5 + epoch/(2*(self.max_evals/self.n))
                if ku<self.surrogate_prob and evals >= self.surrogate_interval+1:
                    is_true_fit = False

                    # Create the model when there was no previously assigned model for surrogate
                    if surrogate_model == None:
                        # Load the text saved before in the training surrogate func. in manager process 
                        surrogate_model = surrogate("krnn",surrogate_X.copy(),surrogate_Y.copy(), self.minx, self.maxx, self.minY, self.maxY, self.path, self.save_surrogate_data, self.surrogate_topology)
                        surrogate_pred, nn_predict = surrogate_model.predict(w_proposal.reshape(1,w_proposal.shape[0]),False)
                        #surrogate_likelihood = surrogate_likelihood *(1.0/self.adapttemp)

                    # Getting the initial predictions if the surrogate model has yet not been initialized     
                    elif self.surrogate_init == 0.0:
                        surrogate_pred,  nn_predict = surrogate_model.predict(w_proposal.reshape(1,w_proposal.shape[0]), False)
                        #print("ENTERED CONDITION 2")
                        #surrogate_likelihood = surrogate_likelihood *(1.0/self.adapttemp)

                    # Getting the predictions if surrogate model is already initialized    
                    else:
                        surrogate_pred,  nn_predict = surrogate_model.predict(w_proposal.reshape(1,w_proposal.shape[0]), True)
                        #print("ENTERED CONDITION 3")
                        #surrogate_likelihood = surrogate_likelihood *(1.0/self.adapttemp)
                    surr_mov_ave = ((surg_fit_list[i])[index_list[i],2] + (surg_fit_list[i])[index_list[i] - 1,2]+ (surg_fit_list[i])[index_list[i] - 2,2])/3
                    surr_proposal = (surrogate_pred * 0.5) + (  surr_mov_ave * 0.5)
                    #surr_proposal = surrogate_pred
                    
                    if self.compare_surrogate is True:
                        fitness_proposal_true = self.fit_func(swarm[i].position)
                    else:
                        fitness_proposal_true = 0
                    #print ('\nSample : ', i, ' Chain :', self.adapttemp, ' -A', likelihood_proposal_true, ' vs. P ',  likelihood_proposal, ' ---- nnPred ', nn_predict, self.minY, self.maxY )
                    surrogate_counter += 1
                    (surg_fit_list[i])[index_list[i]+1,0] =  fitness_proposal_true
                    (surg_fit_list[i])[index_list[i]+1,1]= surr_proposal
                    (surg_fit_list[i])[index_list[i]+1,2] = surr_mov_ave
                else:
                    is_true_fit = True
                    trainset_empty = False
                    (surg_fit_list[i])[index_list[i]+1,1] =  np.nan
                    surr_proposal = self.fit_func(swarm[i].position)
                    fitness_arr = np.array([surr_proposal])
                    if self.surrogate_topology is 4:
                        X, Y = swarm[i].position,fitness_arr
                    else:
                        X, Y = w_proposal,fitness_arr
                    X = X.reshape(1, X.shape[0])
                    Y = Y.reshape(1, Y.shape[0])
                    param_train = np.concatenate([X, Y],axis=1)
                    #surr_train_set = np.vstack((surr_train_set, param_train))
                    (surg_fit_list[i])[index_list[i]+1,0] = surr_proposal
                    (surg_fit_list[i])[index_list[i]+1,2] = surr_proposal

                    surr_train_set[count_real, :] = param_train
                    count_real = count_real +1
                #...................................................# 
                #swarm[i].error = self.fit_func(swarm[i].position)
                swarm[i].error = surr_proposal
                if swarm[i].error < swarm[i].best_part_err:
                    if is_true_fit == True:
                        swarm[i].best_part_err = swarm[i].error
                        swarm[i].best_part_pos = copy.copy(swarm[i].position)

                    else:
                        actual_err = self.fit_func(swarm[i].position)
                        recalc += 1
                        if actual_err < swarm[i].best_part_err:
                            swarm[i].best_part_err = actual_err
                            swarm[i].best_part_pos = copy.copy(swarm[i].position)
                    
                    if swarm[i].best_part_err < best_swarm_err:
                        best_swarm_err = swarm[i].best_part_err
                        best_swarm_pos = copy.copy(swarm[i].position)
                        
                      

                index_list[i] += 1    
                       



            if evals % (self.n)  == 0: 

                train_per, rmse_train = self.classification_perf(best_swarm_pos, 'train')
                test_per, rmse_test = self.classification_perf(best_swarm_pos, 'test')
                print('recalc:',recalc,'evals_no:',evals,' ','epoch_no:', epoch,' ','island_id:',self.island_id,' ','train_perf:', float("{:.3f}".format(train_per)) ,' ','train_rmse:', float("{:.3f}".format(rmse_train)),' ' , 'classification_perf RMSE train * pso' ) 
                #if self.island_id == 1:
                #    self.plots.append(train_per)
                #print(evals, epoch, test_per ,  rmse_test, 'classification_perf  RMSE test * pso' )

            #time.sleep(0.5)    
            ## Sort according to fitness
            swarm = self.sort_swarm(swarm)
            exchange_param = [swarm[k].position for k in range((int)(self.n/5))]
            
            #Swapping and Surrogate data collection Prep        
            if evals % self.surrogate_interval == 0 and evals != 0:
                #Parameter swapping starts
                #param = best_swarm_pos
                param = exchange_param
                self.parameter_queue.put(param)
                ## Surrogate data collection starts
                surr_train = surr_train_set[0:count_real, :]
                print("Total Data Collected in island_id:",self.island_id,":",count_real)
                self.surrogate_parameter_queue.put(surr_train)
                self.signal_main.set()
                self.event.clear()
                self.event.wait()
                result =  self.parameter_queue.get()
                #best_swarm_pos = result 
                #swarm[0].position = best_swarm_pos.copy()
                count_last = 0
                for k in range((int)(8*self.n/10),self.n):
                    swarm[k].position = result[count_last].copy()
                    count_last += 1
                
                model_sign = np.loadtxt(self.path+'/surrogate/model_signature.txt')
                self.model_signature = model_sign
                #print("model_signature updated")

                if self.model_signature==1.0:
                    dummy_X = np.zeros((1,1))
                    dummy_Y = np.zeros((1,1))
                    surrogate_model = surrogate("krnn", dummy_X, dummy_Y, self.minx, self.maxx, self.minY, self.maxY, self.path, self.save_surrogate_data, self.surrogate_topology )

                    local_model_signature = local_model_signature +1  

                # Initialize the surrogate
                self.surrogate_init,  nn_predict  = surrogate_model.predict(best_swarm_pos.reshape(1,best_swarm_pos.shape[0]), False)
                trainset_empty = True 
                #np.savetxt(self.folder+'/surrogate/traindata_'+ str(self.island_id) +'_'+str(local_model_signature)    +'_.txt', surr_train_set)
                count_real = 0      



            epoch += 1
            evals += self.n
      
        train_per, rmse_train = self.classification_perf(best_swarm_pos, 'train')
        test_per, rmse_test = self.classification_perf(best_swarm_pos, 'test')
        #print(evals, epoch, train_per , rmse_train,  'classification_perf RMSE train * pso' )   
        #print(evals, epoch, test_per ,  rmse_test, 'classification_perf  RMSE test * pso' )
        file_name = 'island_results_2/island_'+ str(self.island_id)+ '.txt'
        np.savetxt(file_name, [train_per, rmse_train, test_per, rmse_test], fmt='%1.4f') 
        #.................#

        if self.compare_surrogate is True:
            for i in range(self.n):
                file_name = self.path+'/fitness/surg_fit_list/island_'+ str(self.island_id)+'Particle_'+str(i) + '.txt'
                np.savetxt(file_name,surg_fit_list[i], fmt='%1.4f')
        
        #.................#
        #print(self.plots) 
        #return train_per, test_per, rmse_train, rmse_test
    

        print("Island: {} chain dead!".format(self.island_id))
        self.signal_main.set()
        return    
 
        

        
class distributed_neuroevo:

    def __init__(self,  pop_size, lg_prob,dimen, max_evals,  max_limits, min_limits, netw, traindata, testdata, num_islands,meth,surrogate_topology,use_surrogate,compare_surrogate,save_surrogate_data,path):
        #FNN Chain variables
        self.traindata = traindata
        self.testdata = testdata
        self.topology = netw 
        self.pop_size = pop_size
        self.num_param =  dimen
        self.max_evals = max_evals
        self.max_limits = max_limits
        self.min_limits = min_limits
        self.meth = meth
        self.num_islands = num_islands
        self.islands = [] 
        self.island_numevals = int(self.max_evals/self.num_islands) 
        self.lg_prob = lg_prob

        # create queues for transfer of parameters between process islands running in parallel 
        self.parameter_queue = [multiprocessing.Queue() for i in range(num_islands)]
        self.island_queue = multiprocessing.JoinableQueue()	
        self.wait_island = [multiprocessing.Event() for i in range (self.num_islands)]
        self.event = [multiprocessing.Event() for i in range (self.num_islands)]
        self.swap_interval = 2 * pop_size
        # Surrogate Variables
        self.surrogate_interval = 2 * self.pop_size
        self.surrogate_prob = 0.5
        self.surrogate_resume = [multiprocessing.Event() for i in range(self.num_islands)]
        self.surrogate_start = [multiprocessing.Event() for i in range(self.num_islands)]
        self.surrogate_parameter_queues = [multiprocessing.Queue() for i in range(self.num_islands)]
        self.surrchain_queue = multiprocessing.JoinableQueue()
        self.minY = np.zeros((1,1))
        self.maxY = np.ones((1,1))
        self.model_signature = 0.0
        self.use_surrogate = use_surrogate
        self.surrogate_topology = surrogate_topology
        self.save_surrogate_data =  save_surrogate_data
        self.compare_surrogate = True
        self.path = path
        self.folder = path
        self.total_swap_proposals = 0
        self.num_swaps = 0
        # In case we require surrogate sampling
        self.use_surr_sampling = True


    def initialize_islands(self):
        
        ## for the pso part
        if self.meth == 'PSO':
            for i in range(0, self.num_islands): 
                self.islands.append(neuroevolution(self.pop_size, self.lg_prob,self.num_param, self.island_numevals,  self.max_limits, self.min_limits, self.topology, self.traindata, self.testdata ,self.parameter_queue[i],self.wait_island[i],self.event[i], i, self.swap_interval,self.surrogate_parameter_queues[i],self.surrogate_start[i],self.surrogate_resume[i],self.surrogate_interval,self.surrogate_prob,self.save_surrogate_data,self.use_surrogate,self.compare_surrogate,self.surrogate_topology,self.path))
        
    #Function for swapping the islands upon reaching the swap interval for each chain.
    def swap_procedure(self, parameter_queue_1, parameter_queue_2): 
            param1 = parameter_queue_1.get()
            param2 = parameter_queue_2.get() 
            swap_proposal = 0.5
            u = np.random.uniform(0,1)
            swapped = False
            if u < swap_proposal:   
                param_temp =  param1
                param1 = param2
                param2 = param_temp
                swapped = True 
                self.num_swaps += 1
            else:
                swapped = False 
            self.total_swap_proposals += 1    
            return param1, param2 ,swapped

    #Function for training the surrogate model.        
    def surrogate_trainer(self,params): 

        X = params[:,:self.num_param]
        Y = params[:,self.num_param].reshape(X.shape[0],1)
        num_train = X.shape[0]
        #........................................................#
        #In this section of code we calculate the first four moments of data by creating partitions
        # 1)Expectation 2)Variance(Standard Deviation) 3)Skewness 4)Kurtosis
        
        if(self.surrogate_topology == 4):
            partitions = 10
            X = np.zeros(shape=(num_train,partitions*4))
            if(self.use_surr_sampling == True):
                for k in range(num_train):
                    param_vec = X[k]
                    new_param_vec = []
                    mean_list = []
                    std_list = []
                    skw_list = []
                    krt_list = []
                    chunks = np.array_split(param_vec , partitions)
                    for chunk in chunks:
                        mu = np.mean(chunk)   #Mean
                        std = np.std(chunk)   #Standard-Deviation 
                        skw = skew(chunk)     #skewness
                        krt = kurtosis(chunk)    #Kurtosis
                        mean_list.append(mu)
                        std_list.append(std)
                        skw_list.append(skw)
                        krt_list.append(krt)

                    new_param_vec.extend(mean_list)
                    new_param_vec.extend(std_list)
                    new_param_vec.extend(skw_list)
                    new_param_vec.extend(krt_list) 
                    maxm = max(new_param_vec)
                    minm = min(new_param_vec)   
                    n_param_list = [(i-minm)/(maxm - minm) for i in new_param_vec]
                    X[k] = np.array(n_param_list)
      
        #........................................................#
        self.model_signature += 1.0

        np.savetxt(self.folder+'/surrogate/model_signature.txt', [self.model_signature])
        indices = np.where(Y==np.inf)[0]
        X = np.delete(X, indices, axis=0)
        Y = np.delete(Y,indices, axis=0)
        surrogate_model = surrogate("krnn", X , Y , self.min_limits, self.max_limits, self.minY, self.maxY, self.folder, self.save_surrogate_data, self.surrogate_topology )
        surrogate_model.train(self.model_signature)        
 
 
    def evolve_islands(self): 
        # only adjacent chains can be swapped therefore, the number of proposals is ONE less islands

        self.initialize_islands()
        swap_proposal = np.ones(self.num_islands-1)
 
        # create parameter holders for paramaters that will be swapped
        #replica_param = np.zeros((self.num_islands, self.num_param))  
        #lhood = np.zeros(self.num_islands)
        # Define the starting and ending of MCMC Chains
        start = 0
        end = self.island_numevals
        #number_exchange = np.zeros(self.num_islands) 

        #RUN MCMC CHAINS
        for l in range(0,self.num_islands):
            self.islands[l].start_chain = start
            self.islands[l].end = end 

        for j in range(0,self.num_islands):        
            self.wait_island[j].clear()
            self.event[j].clear()
            self.islands[j].start()
        #SWAP PROCEDURE

        swaps_appected_main =0
        total_swaps_main =0
        #for i in range(int(self.island_numevals/self.swap_interval)):
        for i in range(int(self.island_numevals/self.surrogate_interval)-1):
            count = 0
            # checking if the processes are still alive
            for index in range(self.num_islands):
                if not self.islands[index].is_alive():
                    count+=1
                    self.wait_island[index].set() 

            if count == self.num_islands:
                break 
            print("Waiting for the swapping signals.")
            timeout_count = 0
            for index in range(0,self.num_islands): 
                flag = self.wait_island[index].wait()
                if flag: 
                    timeout_count += 1
            # If signals from all the islands are not received then skip the swap and continue the loop.
            """
            if timeout_count != self.num_islands: 
                print("Skipping the swap")
                continue
            """ 
            if timeout_count == self.num_islands:
                ## Swapping procedure
                for index in range(0,self.num_islands-1): 
                    print('starting swapping')
                    param_1, param_2, swapped = self.swap_procedure(self.parameter_queue[index],self.parameter_queue[index+1])
                    self.parameter_queue[index].put(param_1)
                    self.parameter_queue[index+1].put(param_2)
                    if index == 0:
                        if swapped:
                            swaps_appected_main += 1
                        total_swaps_main += 1
                ## Surrogate data collection
                all_param =   np.empty((1,self.num_param+1))
                for index in range(0,self.num_islands):
                    print('starting surrogate')
                    queue_surr=  self.surrogate_parameter_queues[index] 
                    surr_data = queue_surr.get() 
                    #print("Shape of surr_data:",surr_data.shape)
                    #print("all_param.shape:",all_param.shape)
                    all_param =   np.concatenate([all_param,surr_data],axis=0) 
                print("Shape of all_param Collected :",all_param.shape)
                data_train = all_param[1:,:]  
                print("Shape of Data Collected :",data_train.shape)
                self.surrogate_trainer(data_train) 

                for index in range (self.num_islands):
                        self.event[index].set()
                        self.wait_island[index].clear()

            elif timeout_count == 0:
                break
            else:
                print("Skipping the swap")             

            
            
        for index in range(0,self.num_islands):
            self.islands[index].join()
        self.island_queue.join()
        for i in range(0,self.num_islands):
            #self.parameter_queue[i].close()
            #self.parameter_queue[i].join_thread()
            self.surrogate_parameter_queues[i].close()
            self.surrogate_parameter_queues[i].join_thread()


        train_per, test_per, rmse_train, rmse_test, train_per_std, test_per_std, rmse_train_std, rmse_test_std,surr_rmse = self.get_results()
        #swapping_percent = self.num_swap*100/self.total_swap_proposals
        #print("Swapping_Percent:",swapping_percent)


        return   train_per, test_per, rmse_train, rmse_test, train_per_std, test_per_std, rmse_train_std, rmse_test_std,surr_rmse

    # Credits : https://stackoverflow.com/questions/15033511/compute-a-confidence-interval-from-sample-data
    def get_confidence(self,data):
      conf = 0.95
      a = 1.0 * np.array(data)
      n = len(a)
      se = scipy.stats.sem(a)
      interv = se * scipy.stats.t.ppf((1 + conf) / 2., n-1)
      return interv

    def Plot_bars(self,surrogate_fit):
      eval_interval = (int)(self.max_evals/20)
      width = (int)(self.max_evals/100) + 100
      labels = []
      labels_cnt = eval_interval
      while labels_cnt<= surrogate_fit.shape[0]:
        labels = np.concatenate((labels,[labels_cnt]))
        labels_cnt += eval_interval
      part = (int)(surrogate_fit.shape[0]/eval_interval)
      slice_idx = (int)(part*eval_interval)
      fit_partition = np.array_split(surrogate_fit[:slice_idx,:] ,part)  
      surr_mean = []
      surr_std = []
      actual_mean = []
      actual_std = []
      for chunk in fit_partition:
        surr_mean.append(np.mean(chunk[:,1]))
        actual_mean.append(np.mean(chunk[:,0]))
        surr_std.append(self.get_confidence(chunk[:,1]))
        actual_std.append(self.get_confidence(chunk[:,0]))
        #surr_std.append(np.std(chunk[:,1]))
        #actual_std.append(np.std(chunk[:,0]))
      r1 = [(int)(lab) for lab in labels]
      r2 = [(int)(x + width) for x in r1]
      fig, ax = plt.subplots()
      #size = 15
      # Creating +- 95% confidence interval around mean according to Gaussian Curve 
      rects1 = ax.bar(r1, np.array(surr_mean), width,edgecolor = 'black', yerr= np.array(surr_std), capsize=2, label='Surrogate Fitness')
      rects2 = ax.bar(r2, np.array(actual_mean), width,edgecolor = 'black', yerr= np.array(actual_std),capsize=2,  label='True Fitness')
      #plt.tick_params(labelsize=size)
      #params = {'legend.fontsize': size, 'legend.handlelength': 2}
      #plt.rcParams.update(params)
      plt.title(" Fitness Comparison ")
      plt.xlabel('Surrogate Evaluations')
      plt.ylabel('Fitness(Mean)')
      labels_int = [(int)(lab) for lab in labels]
      plt.xticks([(int)(r + width/2) for r in labels], labels_int)
      plt.setp(ax.get_xticklabels(), fontsize=9)
      ax.legend()
      fig.tight_layout()
      plt.savefig('%s/surr_actual_bar.pdf'% (self.path), dpi=300)
      #plt.show()



    def get_results(self):

        res_collect = np.zeros((self.num_islands,4))
        
         
        for i in range(self.num_islands):
            file_name = 'island_results_2/island_'+ str(i)+ '.txt'
            dat = np.loadtxt(file_name)
            res_collect[i,:] = dat 

        print(res_collect, ' res_collect')

        train_per = np.mean(res_collect[:,0])
        train_per_std = np.std(res_collect[:,0])

        rmse_train = np.mean(res_collect[:,1])
        rmse_train_std = np.std(res_collect[:,1])

        test_per = np.mean(res_collect[:,2])
        test_per_std = np.std(res_collect[:,2])

        rmse_test = np.mean(res_collect[:,3])
        rmse_test_std = np.std(res_collect[:,3])
        #..........................................#
        # This segment of code uses the surg_fit_list saved for plotting and comparing the 
        # surrogate fitness vs actual fitness.
        gen_value = (int)(self.island_numevals/self.pop_size)
        surg_compare = np.zeros((self.num_islands*self.pop_size ,gen_value ,2))
        rmse_surr = 0

        if self.compare_surrogate is True:
            """
            counter = 0
            for k in range(self.num_islands):
                for i in range(self.pop_size):
                    file_name = self.path+'/fitness/surg_fit_list/island_'+ str(k)+'Particle_'+str(i) + '.txt'
                    dat = np.loadtxt(file_name) 
                    surg_compare[counter, :]  = dat[1:,0:2]
                    counter += 1
            """
            counter = 0
            for k in range(self.num_islands):
                for i in range(self.pop_size):
                    file_name = self.path+'/fitness/surg_fit_list/island_'+ str(k)+'Particle_'+str(i) + '.txt'
                    dat = np.loadtxt(file_name) 
                    surg_compare[counter, :]  = dat[1:,0:2]
                    counter += 1   
            
            surg_fit_vec = surg_compare.transpose(2,0,1).reshape(2,-1)
            rmse_surr =0
            surr_list = []
            surr_list = surg_fit_vec.T
            surrogate_fit = surg_fit_vec.T
            
            #print("Surrogate_fit1:",surrogate_fit.shape)
            surrogate_fit = surrogate_fit[~np.isnan(surrogate_fit).any(axis=1)]
            #print("Surrogate_fit2:",surrogate_fit.shape)
            rmse_surr =  np.sqrt(((surrogate_fit[:,1]-surrogate_fit[:,0])**2).mean())
            #print("rmse_surr:", rmse_surr)
            plot_step = 25
            plot_i = 0
            splitted_plot = np.empty((1,2))
            slen = []
            while plot_i<surrogate_fit.shape[0]:
              slen.append(plot_i)
              splitted_plot = np.concatenate([splitted_plot , surrogate_fit[plot_i].reshape(1,2)], axis =0)
              plot_i += plot_step
            splitted_plot = splitted_plot[1:,:]  
            #slen = np.arange(0,surrogate_fit.shape[0],1)
            # 1.Bar Plots with confidence intervals
            self.Plot_bars(surrogate_fit)

            # 2.Surrogate vs Actual Fitness over number of surrogate evaluations
            slen = np.array(slen)
            fig = plt.figure(figsize = (12,12))
            ax = fig.add_subplot(111) 
            plt.tick_params(labelsize=25)
            params = {'legend.fontsize': 25, 'legend.handlelength': 2}
            plt.rcParams.update(params)
            surrogate_plot = ax.plot(slen,splitted_plot[:,1],linestyle='-', linewidth= 1, color= 'b', label= 'Surrogate ')
            model_plot = ax.plot(slen,splitted_plot[:,0],linestyle= '--', linewidth = 1, color = 'k', label = 'True')

            #residuals =  surrogate_likl[:,0]- surrogate_likl[:,1]
            #res = ax.plot(slen, residuals,linestyle= '--', linewidth = 1, color = 'r', label = 'Residuals')
            ax.set_xlabel('Surrogate Evaluations',size= 25)
            ax.set_ylabel(' Fitness', size= 25)
            ax.set_xlim([0,np.amax(slen)]) 
  
            ax.legend(loc='best')
            fig.tight_layout()
            fig.subplots_adjust(top=0.88)
            plt.savefig('%s/surrogate_fitness.pdf'% (self.path), dpi=300, transparent=False)
            plt.clf()
  
            np.savetxt(self.path + '/surrogate/surg_fit.txt', surrogate_fit, fmt='%1.5f')


        return   train_per, test_per, rmse_train, rmse_test, train_per_std, test_per_std, rmse_train_std, rmse_test_std,rmse_surr





def main():
    print("Starting to run....")
    method = 'PSO'
    problem = int(sys.argv[1])
    lg_prob = float(sys.argv[2])
    for runs in range(1):
         
        separate_flag = False # dont change 

        if problem == 3: #IRIS
            data  = np.genfromtxt('DATA/iris.csv',delimiter=';')
            classes = data[:,4].reshape(data.shape[0],1)-1
            features = data[:,0:4]
            separate_flag = True
            name = "iris"
            hidden = 8  #12
            ip = 4 #input
            output = 3 
            max_evals = 20000
            surrogate_topology = 1

        if problem == 4: #Ionosphere
            traindata = np.genfromtxt('DATA/Ions/Ions/ftrain.csv',delimiter=',')[:,:-1]
            testdata = np.genfromtxt('DATA/Ions/Ions/ftest.csv',delimiter=',')[:,:-1]
            name = "Ionosphere"
            hidden = 15 #50
            ip = 34 #input
            output = 2 
            max_evals = 30000
            surrogate_topology = 1

            #NumSample = 50000
        if problem == 5: #Cancer
            traindata = np.genfromtxt('DATA/Cancer/ftrain.txt',delimiter=' ')[:,:-1]
            testdata = np.genfromtxt('DATA/Cancer/ftest.txt',delimiter=' ')[:,:-1]
            name = "Cancer"
            hidden = 8 # 12
            ip = 9 #input
            output = 2 
            max_evals = 20000
            surrogate_topology = 1

            # print(' cancer')

        if problem == 6: #Bank additional
            data = np.genfromtxt('DATA/Bank/bank-processed.csv',delimiter=';')
            #classes = data[:,20].reshape(data.shape[0],1)
            #features = data[:,0:20]
            classes = data[:,51].reshape(data.shape[0],1)
            features = data[:,0:51]
            separate_flag = True
            name = "bank-additional"
            hidden = 90# 50
            ip = 51# 20 #input
            output = 2 
            max_evals = 50000
            surrogate_topology = 2

        if problem == 7: #PenDigit
            traindata = np.genfromtxt('DATA/PenDigit/train.csv',delimiter=',')
            testdata = np.genfromtxt('DATA/PenDigit/test.csv',delimiter=',')
            name = "PenDigit"
            for k in range(16):
                mean_train = np.mean(traindata[:,k])
                dev_train = np.std(traindata[:,k])
                traindata[:,k] = (traindata[:,k]-mean_train)/dev_train
                mean_test = np.mean(testdata[:,k])
                dev_test = np.std(testdata[:,k])
                testdata[:,k] = (testdata[:,k]-mean_test)/dev_test
            ip = 16
            hidden = 30
            output = 10 
            max_evals = 50000
            surrogate_topology = 2

        if problem == 8: #Chess
            data  = np.genfromtxt('DATA/chess.csv',delimiter=';')
            classes = data[:,6].reshape(data.shape[0],1)
            features = data[:,0:6]
            separate_flag = True
            name = "chess"
            hidden = 25
            ip = 6 #input
            output = 18 
            max_evals = 50000
            surrogate_topology = 3

        
        #Separating data to train and test
        if separate_flag is True:
            #Normalizing Data
            for k in range(ip):
                mean = np.mean(features[:,k])
                dev = np.std(features[:,k])
                features[:,k] = (features[:,k]-mean)/dev
            train_ratio = 0.6 #Choosable
            indices = np.random.permutation(features.shape[0])
            traindata = np.hstack([features[indices[:np.int(train_ratio*features.shape[0])],:],classes[indices[:np.int(train_ratio*features.shape[0])],:]])
            testdata = np.hstack([features[indices[np.int(train_ratio*features.shape[0])]:,:],classes[indices[np.int(train_ratio*features.shape[0])]:,:]])



        topology = [ip, hidden, output] 
        use_surrogate = True
        save_surrogate_data = False
        compare_surrogate = True
        netw = topology
        y_test =  testdata[:,netw[0]]
        y_train =  traindata[:,netw[0]]
        print(y_train)

        #path_results = 'results/' + name +'/results_new.txt'
        #outfile_pso=open(path_results,'a+')
        path_temp = 'results/' + name +'/temp.txt'
        outfile_temp = open(path_temp,'a+')

        num_varibles = (netw[0] * netw[1]) + (netw[1] * netw[2]) + netw[1] + netw[2]  # num of weights and bias
        print("num_variables: ",num_varibles)
        max_limits = np.repeat(50, num_varibles) 
        min_limits = np.repeat(-50, num_varibles)

        print(traindata)

        problemfolder = 'surr_results/'
        run_nb = 0
        path = (problemfolder+name+'_%s' % (run_nb))
        if not os.path.exists( problemfolder+name+'_%s' % (run_nb)):
            os.makedirs(  problemfolder+name+'_%s' % (run_nb))
            path = (problemfolder+ name+'_%s' % (run_nb))

        pop_size = 50
        num_islands = 10# currently testing on 10 islands using multiprocessing.
            
        timer = time.time()
        neuroevolution =  distributed_neuroevo(pop_size,lg_prob ,num_varibles, max_evals,  max_limits, min_limits, netw, traindata, testdata, num_islands,method,surrogate_topology,use_surrogate,compare_surrogate,save_surrogate_data,path)
        train_per, test_per, rmse_train, rmse_test, train_per_std, test_per_std, rmse_train_std, rmse_test_std, rmse_surr= neuroevolution.evolve_islands()

        print('train_perf: ',float("{:.3f}".format(train_per)) ,'rmse_train: ' ,float("{:.3f}".format(rmse_train)),  'classification_perf RMSE train * pso' )   
        print('test_perf: ',float("{:.3f}".format(test_per)) , 'rmse_test: ' ,float("{:.3f}".format(rmse_test)), 'classification_perf  RMSE test * pso' )

        timer2 = time.time()
        timetotal = (timer2 - timer) /60
        allres =  np.asarray([train_per, test_per, timetotal,rmse_surr]) 
        np.savetxt(outfile_temp,  allres   , fmt='%1.4f', newline='  '  )
        np.savetxt(outfile_temp,  [' Surrogate_PSO Gradient_Prob: '+str(lg_prob)], fmt="%s", newline=' \n '  )
                


            
            
         

if __name__ == "__main__": main()
