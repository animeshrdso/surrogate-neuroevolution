# !/usr/bin/python
import matplotlib.pyplot as plt
import numpy as np
from numpy import linalg as LA
from scipy.linalg import sqrtm
#from numpy.random import default_rng
np.set_printoptions(suppress=True)
import random
from random import seed
import time
import math
import os
import shutil

import multiprocessing 
import gc
  
import copy    # array-copying convenience
import sys     # max float

from pyDOE import *
np.seterr(divide='ignore', invalid='ignore')
# -----------------------------------

# using https://github.com/sydney-machine-learning/canonical_neuroevolution

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
class particle(evaluate_neuralnetwork):
    def __init__(self,  dim,  maxx, minx, netw, traindata, testdata, id_island):
        evaluate_neuralnetwork.__init__( self, netw, traindata, testdata) # inherits neuroevolution class definition and methods

        

        np_pos = np.random.rand(dim)#/2 + r_pos/2
        np_vel = np.random.rand(dim)#/2 + r_pos/2
        

        self.position = ((maxx - minx) * np_pos  + minx) # using random.rand() rather than np.random.rand() to avoid multiprocesssing random issues
        self.velocity = ((maxx - minx) * np_vel  + minx)


        self.error =  self.fit_func(self.position) # curr error
        self.best_part_pos =  self.position.copy()
        self.best_part_err = self.error # best error 



class neuroevolution(evaluate_neuralnetwork, multiprocessing.Process):  # PSO http://www.scholarpedia.org/article/Particle_swarm_optimization
    def __init__(self, name,pop_size, lg_prob,dimen, max_evals,  max_limits, min_limits, netw, traindata, testdata, parameter_queue, wait_chain, event, island_id, swap_interval):
        
        multiprocessing.Process.__init__(self) # set up multiprocessing class

        evaluate_neuralnetwork.__init__( self, netw, traindata, testdata) # sepossiesiont up - inherits neuroevolution class definition and methods

        self.parameter_queue = parameter_queue
        self.signal_main = wait_chain
        self.event =  event
        self.island_id = island_id
        self.dim = dimen
        self.n = pop_size
        self.minx = min_limits
        self.maxx = max_limits
        self.max_evals = max_evals
        self.netw = netw
        self.lg_prob = lg_prob
        self.traindata = traindata
        self.testdata = testdata
        self.swap_interval = swap_interval
        self.name = name
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
        np.random.seed(int(self.island_id) )
        swarm = [particle(self.dim, self.minx, self.maxx,  self.netw, self.traindata, self.testdata, self.island_id) for i in range(self.n)] 
        best_swarm_pos = [0.0 for i in range(self.dim)] # not necess.
        best_swarm_err = sys.float_info.max # swarm best
        for i in range(self.n): # check each particle
            #print(swarm[i].position[0:4], self.island_id, i)
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
        if self.island_id == 1 or self.island_id == 3 or self.island_id == 5 or self.island_id == 7:
          mean_list = []
          plot_list = []
          best_list = []
          x_tik = []
          ctr = 0
        self.event.clear()
        while evals < (self.max_evals ):
            
            for i in range(self.n): # process each particle 

                #r_pos = np.asarray(random.sample(range(1, self.dim+1), self.dim) )/ (self.dim+1) #to force using random without np and convert to np (to avoid multiprocessing random seed issue)
 
                r1 = np.random.rand(self.dim)#/2 + r_pos/2
                r2 = np.random.rand(self.dim)
                swarm[i].velocity = ( (w * swarm[i].velocity) + (c1 * r1 * (swarm[i].best_part_pos - swarm[i].position)) +  (c2 * r2 * (best_swarm_pos - swarm[i].position)) )  
                swarm[i].position += swarm[i].velocity
                u = random.uniform(0, 1)
                #depth = random.randint(1, 5)# num of epochs for gradients by backprop
                #swarm[i].position += np.random.normal(0.0,2,self.dim)
                depth = 1
                if u < gradient_prob and use_gradients == True: 
                    swarm[i].position = self.neuro_gradient(self.traindata, swarm[i].position.copy(), depth)  
                    
                for k in range(self.dim): 
                    if swarm[i].position[k] < self.minx[k]:
                        swarm[i].position[k] = self.minx[k]
                    elif swarm[i].position[k] > self.maxx[k]:
                        swarm[i].position[k] = self.maxx[k]

                swarm[i].error = self.fit_func(swarm[i].position)

                if swarm[i].error < swarm[i].best_part_err:
                    swarm[i].best_part_err = swarm[i].error
                    swarm[i].best_part_pos = copy.copy(swarm[i].position)     

                if swarm[i].error < best_swarm_err:
                    best_swarm_err = swarm[i].error
                    best_swarm_pos = copy.copy(swarm[i].position)


                #print(' **  ', i, evals, epoch, best_swarm_err, self.island_id)

            if evals % (self.n*2)  == 0: 

                train_per, rmse_train = self.classification_perf(best_swarm_pos, 'train')
                test_per, rmse_test = self.classification_perf(best_swarm_pos, 'test')
                print('evals_no:',evals,' ','epoch_no:', epoch,' ','island_id:',self.island_id,' ','train_perf:', float("{:.3f}".format(train_per)) ,' ','train_rmse:', float("{:.3f}".format(rmse_train)),' ' , 'classification_perf RMSE train * pso' ) 
                #if self.island_id == 1:
                #    self.plots.append(train_per)
                #print(evals, epoch, test_per ,  rmse_test, 'classification_perf  RMSE test * pso' )

            
            
            if self.island_id == 1 or self.island_id == 3 or self.island_id == 5 or self.island_id == 7:
              fit_list = [swarm[i].error for i in range(self.n)]
              mean_f = np.mean(fit_list)
              ct = 0
              while ct<self.n:
                mean_list.append(mean_f)
                plot_list.append(copy.deepcopy(swarm[ct].error))
                best_list.append(copy.deepcopy(best_swarm_err))
                x_tik.append(ctr)
                ct += 10
                ctr += 10    
            ## Sort according to fitness
            swarm = self.sort_swarm(swarm)
            exchange_param = [swarm[k].position for k in range((int)(self.n/5))]

            if (evals % self.swap_interval == 0 ): # interprocess (island) communication for exchange of neighbouring best_swarm_pos
                #param = best_swarm_pos
                param = exchange_param
                self.parameter_queue.put(param)
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


            epoch += 1
            evals += self.n
 

        train_per, rmse_train = self.classification_perf(best_swarm_pos, 'train')
        test_per, rmse_test = self.classification_perf(best_swarm_pos, 'test')
        file_name = 'island_results_2/island_'+ str(self.island_id)+ '.txt'
        np.savetxt(file_name, [train_per, rmse_train, test_per, rmse_test], fmt='%1.4f') 

        if self.island_id == 1 or self.island_id == 3 or self.island_id == 5 or self.island_id == 7:
          path = 'results/' + self.name
          fig,ax = plt.subplots()
          ax.plot(x_tik , plot_list , '-r*' , label = 'Individual Particle movement')
          ax.plot(x_tik , mean_list , '-b*' , label = 'Mean Particle movement')
          ax.plot(x_tik , best_list , '-g*',label = 'Best Particle Movement')
          plt.xlabel('Evaluations per Island')
          plt.ylabel('Fitness of Particles')
          plt.title('Island Number: ' + str(self.island_id + 1))
          #ax.legend(['Individual Particle movement' , 'Best Particle Movement'])
          ax.legend()
          fig.tight_layout()
          plot_file = path + '/swarm_mov_' + str(self.island_id) + '.png'
          plt.savefig(plot_file, dpi=300)
          #plt.show()
        #print(self.plots) 
        #return train_per, test_per, rmse_train, rmse_test

        
class distributed_neuroevo:

    def __init__(self,  pop_size, lg_prob,dimen, max_evals,  max_limits, min_limits, netw, traindata, testdata, num_islands,meth,name):
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
        self.name = name
        self.lg_prob = lg_prob
        self.num_islands = num_islands

        self.islands = [] 
        self.island_numevals = int(self.max_evals/self.num_islands) 

        # create queues for transfer of parameters between process islands running in parallel 
        self.parameter_queue = [multiprocessing.Queue() for i in range(num_islands)]
        self.island_queue = multiprocessing.JoinableQueue()	
        self.wait_island = [multiprocessing.Event() for i in range (self.num_islands)]
        self.event = [multiprocessing.Event() for i in range (self.num_islands)]


        self.swap_interval = 2 * pop_size


    def initialize_islands(self ):
        
        ## for the pso part
        if self.meth == 'PSO':
            for i in range(0, self.num_islands): 
                self.islands.append(neuroevolution( self.name, self.pop_size, self.lg_prob,self.num_param, self.island_numevals,  self.max_limits, self.min_limits, self.topology, self.traindata, self.testdata ,self.parameter_queue[i],self.wait_island[i],self.event[i], i, self.swap_interval))
        
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
            else:
                swapped = False 
            return param1, param2 ,swapped
 
 
    def evolve_islands(self): 
        # only adjacent chains can be swapped therefore, the number of proposals is ONE less islands

        self.initialize_islands()


        #swap_proposal = np.ones(self.num_islands-1)
 
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
        for i in range(int(self.island_numevals/self.swap_interval)):
            count = 0
            for index in range(self.num_islands):
                if not self.islands[index].is_alive():
                    count+=1
                    self.wait_island[index].set() 

            if count == self.num_islands:
                break 

            timeout_count = 0
            for index in range(0,self.num_islands): 
                flag = self.wait_island[index].wait()
                if flag: 
                    timeout_count += 1

            if timeout_count != self.num_islands: 
                continue 

            for index in range(0,self.num_islands-1): 
                param_1, param_2, swapped = self.swap_procedure(self.parameter_queue[index],self.parameter_queue[index+1])
                self.parameter_queue[index].put(param_1)
                self.parameter_queue[index+1].put(param_2)
                if index == 0:
                    if swapped:
                        swaps_appected_main += 1
                    total_swaps_main += 1
            for index in range (self.num_islands):
                    self.event[index].set()
                    self.wait_island[index].clear() 

        for index in range(0,self.num_islands):
            self.islands[index].join()
        self.island_queue.join()


        train_per, test_per, rmse_train, rmse_test, train_per_std, test_per_std, rmse_train_std, rmse_test_std = self.get_results()


        return   train_per, test_per, rmse_train, rmse_test, train_per_std, test_per_std, rmse_train_std, rmse_test_std







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
        
        
        




        return   train_per, test_per, rmse_train, rmse_test, train_per_std, test_per_std, rmse_train_std, rmse_test_std





def main():

    print("Starting to run....")
    method = 'PSO'
    problem = int(sys.argv[1])
    lg_prob = float(sys.argv[2])
    for runs in range(1) :        
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
        if problem == 4: #Ionosphere
            traindata = np.genfromtxt('DATA/Ions/Ions/ftrain.csv',delimiter=',')[:,:-1]
            testdata = np.genfromtxt('DATA/Ions/Ions/ftest.csv',delimiter=',')[:,:-1]
            name = "Ionosphere"
            hidden = 15 #50
            ip = 34 #input
            output = 2 
            max_evals = 30000

            #NumSample = 50000
        if problem == 5: #Cancer
            traindata = np.genfromtxt('DATA/Cancer/ftrain.txt',delimiter=' ')[:,:-1]
            testdata = np.genfromtxt('DATA/Cancer/ftest.txt',delimiter=' ')[:,:-1]
            name = "Cancer"
            hidden = 8 # 12
            ip = 9 #input
            output = 2 
            max_evals = 20000

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
        netw = topology
        y_test =  testdata[:,netw[0]]
        y_train =  traindata[:,netw[0]]

        print(y_train)
        #path_results = 'results/' + name +'/results_new.txt'
        #outfile_pso=open(path_results,'a+')
        path_temp = 'results/' + name +'/temp.txt'
        outfile_temp = open(path_temp,'a+')
        num_varibles = (netw[0] * netw[1]) + (netw[1] * netw[2]) + netw[1] + netw[2]  # num of weights and bias
        max_limits = np.repeat(50, num_varibles) 
        min_limits = np.repeat(-50, num_varibles)
        print(traindata)  
        pop_size = 50
        num_islands = 10# currently testing on 10 islands using multiprocessing.
        timer = time.time()
        neuroevolution =  distributed_neuroevo(pop_size, lg_prob,num_varibles, max_evals,  max_limits, min_limits, netw, traindata, testdata, num_islands,method,name)
        train_per, test_per, rmse_train, rmse_test, train_per_std, test_per_std, rmse_train_std, rmse_test_std = neuroevolution.evolve_islands()
        print('train_perf: ',float("{:.3f}".format(train_per)) ,'rmse_train: ' ,float("{:.3f}".format(rmse_train)),  'classification_perf RMSE train * pso' )   
        print('test_perf: ',float("{:.3f}".format(test_per)) , 'rmse_test: ' ,float("{:.3f}".format(rmse_test)), 'classification_perf  RMSE test * pso' )
        timer2 = time.time()
        timetotal = (timer2 - timer) /60
        allres =  np.asarray([train_per, test_per, timetotal]) 
        np.savetxt(outfile_temp,  allres   , fmt='%1.4f', newline='  '  )
        np.savetxt(outfile_temp,  [' PSO Gradient_Prob: '+str(lg_prob)], fmt="%s", newline=' \n '  )
            

      


if __name__ == "__main__": main()
