#!/bin/sh 
echo Running all 	 
 
for size in  10000 
 	do
	for optim in 0 1
  		do
		for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30
			do   
			python adam_sgd_cnn.py $size $optim
  
  
	done  
		
	done
done
