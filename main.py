###########################################################################################
# project: Tichu software
# author: Johannes Knoerzer
# created: Jan 29, 2021
###########################################################################################

# TROUBLEASHOOTING:
# - when one player finishes, another player was kicked out of the game
# - 

###########################################################################################
# List of To Dos:
# (0) write exceptions
# (1) missing combinations: n consecutive pairs, straight
# (2) implement Dog.
# (3) implement Phoenix.
# (4) implement points for teams (will be used for cost function later)
# (5) implement Dragon.
# (6) bombs (most importantly, can be played anytime! problem with existing apps)
# (7) implement bets
# (8)
###########################################################################################

###########################################################################################
# LIBRARIES
import random
import sys
import numpy as np
from itertools import product
###########################################################################################

ver = 0.1
print("Welcome to Tichu version %.1f" % (ver))


###########################################################################################
# CARD class
###########################################################################################
class Card:
	suits = ['Red', 'Black', 'Blue', 'Green', 'Special']
	ranks = ['Dogs', '1 (Mahjong)', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', 'Phoenix', 'Dragon']
	
	def __init__(self, suit, rank):
		self.suit = suit
		self.rank = rank
	
	def show(self):
		if self.rank <= 14 and self.rank >= 2:
			print("{} {}".format(Card.suits[self.suit],Card.ranks[self.rank]))
		else:
			print("{}".format(Card.ranks[self.rank]))


###########################################################################################
# DECK class
###########################################################################################
class Deck:
	def __init__(self):
		self.cards = []
		for suit in range(4):
			for rank in range(2,15):
				card = Card(suit, rank)
				self.cards.append(card)
		
		for rank in [0,1,15,16]:
			card = Card(4, rank)
			self.cards.append(card)
		
		self.shuffle()
	
	def shuffle(self):
		random.shuffle(self.cards)
		
	def show(self):
		for c in self.cards:
			c.show()
			
	def draw(self):
		return self.cards.pop()


###########################################################################################
# PLAYER class
###########################################################################################
class Player:
	combos = ['high card', 'pair', 'three of a kind', 'full house', 'n pairs', 'straight', 'bomb', 'dog']
	actions = ['You come first. Play a combination of your choice.',
	'You can either play a higher card/combination or pass.',
	'You cannot play. You have to pass.',
	'It is not your turn.'] 
	
	def __init__(self,name,number,team):
		self.name = name
		self.number = number
		self.team = team
		self.hand = []
		self.stack = []
		self.combo = [[0 for x in range(18)], [0 for x in range(14)], [0 for x in range(14)], [0 for x in range(13*13)], [0 for x in range(13*12/2)], [0 for x in range(9*10/2)], [0 for x in range(1)]]
		self.possibleCombos = [False for i in range(7)]
		self.possibleCombos[0] = True
		self.toDiscard = []
		self.possibleActions = 3
		self.active = True
		self.tichuBet = False
		self.tichuGrandBet = False
		self.points = 0
		
	def askBot(self):
		return 0	
	
	def draw(self, deck):
		self.hand.append(deck.draw())	
		
	def getFullHouse(self,ind):
		# this function returns the Full House in an array of length two, given an index of combination
		indThree = int(ind/13)
		indPair = ind%13
		return [indThree+2,indPair+2]
	
	def getConnectedPairs(self,ind):
		indSmallest = int(ind/13)
		indLargest = int(ind/13)+1+ind%13
		return [indSmallest+2,indLargest+2]
				
	def show(self):
		for c in self.hand:
			c.show()
	
	def checkCard(self,suitsCheck,rankCheck):
		cardIndex = 100
		ind = 0
		for c in self.hand:
			if c.suit == suitsCheck and c.rank == rankCheck:
				cardIndex = ind
			ind += 1
		return cardIndex
			
	def discard(self,suits,rank):
		discardIndex = self.checkCard(suits,rank)
		if(discardIndex!=100):
			self.toDiscard.append(discardIndex)
		else:
			print("Error. No possible combo.")
		
	def checkCombo(self): # rename this function: playCombo instead of checkCombo
		
		# Existing combinations in Tichu:
		# (1) high card
		# (2) two of a kind (pair)
		# (3) three of a kind
		# (4) full house
		# (5) n pairs
		# (6) straight
		# ((7)) bombs (leave for later)
		
		for a in self.toDiscard:
			self.hand.pop(a)
			# ~ print(a)
			# ~ print(len(self.hand))
			for j in range(len(self.toDiscard)):
				if self.toDiscard[j]>a:
					self.toDiscard[j]-=1
		
		self.toDiscard = []
		
	def checkBomb(self): # to do: check if bomb avail
		return False
		
	def findMatching(self,ind): # redundant. can be gotten rid of since we have "checkCard"
		matchingSuits = []
		for i in range(len(self.hand)):
			if self.hand[i].rank == ind:
				matchingSuits.append(self.hand[i].suit)
		return matchingSuits
	
	def checkPossibleCombos(self,writeOut=True):
		
		for a in range(1,7):
			self.possibleCombos[a] = False
		
		self.combo = [[0 for x in range(18)], [0 for x in range(14)], [0 for x in range(14)], [0 for x in range(13*13)], [0 for x in range(13*12)], [0 for x in range(9*10/2)], [0 for x in range(1)]]
		
		for x in self.hand: # to do: take color into account (only important for bombs)
			self.combo[0][x.rank] += 1
			
		# ~ print(self.combo)
		
		# include phoenix here! (add additional list of phoenix-assisted combinations)
		
		# find pairs
		for j in range(2,15):
			if self.combo[0][j] > 1:
				self.combo[1][j-2] = 1
				self.possibleCombos[1] = True
				
		# find three of a kind
		for j in range(2,15):
			if self.combo[0][j] > 2:
				self.combo[2][j-2] = 1
				self.possibleCombos[2] = True
				
		# find full house
		for j in range(2,15):
			for k in range(2,15):
				if self.combo[1][j-2] == 1 and self.combo[2][k-2] == 1 and j != k:
					self.combo[3][(k-2)*13+(j-2)] = 1
					self.possibleCombos[3] = True
		
		# find n consecutive pairs (n > 1)
		for j in range(2,14):
			if self.combo[1][j-2] == 1:
				n = 1
				chainActive = True
				while chainActive:
					if self.combo[1][j-2+n] == 1:
						self.combo[4][(j-2)*13+(n-1)] = 1
						self.possibleCombos[4] = True
						n+=1
					else:
						chainActive = False
						
		# j+n
		
		
		# find straight (first: without flush and without phoenix)
		for j in range(2,14):
			if self.combo[0][j] == 1:
				n = 1
				straightActive = True
				while straightActive:
					if self.combo[0][j+n] != 1 or j+n > 14:
						straightActive = False
					else:
						n += 1
					
					if n >= 5:
						self.combo[5][j-2+n-5] = 1
						self.possibleCombos[5] = True
				
		
		if(writeOut==True):
			for a in range(7):
				if self.possibleCombos[a] == True:
					print("You can play " + self.combos[a] + " (" + str(a) + ")")


###########################################################################################
# ROUND class
###########################################################################################
class Round:
	def __init__(self,number,leadPlayer,players):
		self.number = number
		self.leadPlayer = leadPlayer # player who comes first in new round
		self.currPlayer = 0
		self.currComb = 0
		self.currCard = 0
		self.points1 = 0
		self.points2 = 0
		self.teamPoints = [self.points1, self.points2]
		self.passedCounter = 0
		self.activePlayers = 4
		self.players = players
		self.currLead = 0 # player who played out last
		self.trickPoints = 0 # point counter per trick
		self.dragonWins = False
		
	def nextActivePlayer(self):
		playersWithCards = []
		for j in range(1,4):
			if(len(self.players[(self.currPlayer+j)%4].hand) > 0):
				playersWithCards.append(j)
				
		return (self.currPlayer+min(playersWithCards))%4
				
	def findActivePlayer(self,playerIndex):
		playersWithCards = []
		for j in range(1,4):
			if(len(self.players[(playerIndex+j)%4].hand) > 0):
				playersWithCards.append(j)
			
		return (playerIndex+min(playersWithCards))%4
		
	def earnCards(self,winner):
		winner.points += self.trickPoints
		#add dragon
		


###########################################################################################
# startTurn METHOD: the mechanics of the game is encoded here	
###########################################################################################
def startTurn(player,game):
	print(" \nHand of " + str(player.name) + ":")
	player.show()
	# ~ print(" \nPossible combinations:")
	# ~ player.checkPossibleCombos()
	print(" \n" + player.name + ", here's what you can do:")
	print(player.actions[player.possibleActions])
	
	# Current player comes first
	if(player.possibleActions == 0):
		print(" \nWhat do you want to bet?")
		player.checkPossibleCombos()
		game.currComb = input()
		
		# Show available combinations			
		print(" \nAvailable " + str(player.combos[game.currComb]) + ":")
		for k in range(len(player.combo[game.currComb][:])):
			if player.combo[game.currComb][k] >= 1:
				if(game.currComb == 0):
					print(Card.ranks[k] + " \n")					
				elif(game.currComb == 1):
					print(Card.ranks[k+2] + " \n")
				elif(game.currComb == 2):
					print(Card.ranks[k+2])
				elif(game.currComb == 3):
					print("Three of " + Card.ranks[player.getFullHouse(k)[0]] + ", two of " + Card.ranks[player.getFullHouse(k)[1]] + "(" + str(k) + ")")
				elif(game.currComb == 4):
					print("Smallest pair is " + Card.ranks[player.getConnectedPairs(k)[0]] + " and largest is " + Card.ranks[player.getConnectedPairs(k)[1]] + "(" + str(k) + ")")

		# They want to play a single card:
		if(game.currComb == 0):		
			print(" \nRank:")
			inputRank = input()
			
			game.currCard = inputRank
			
			for j in range(len(player.findMatching(inputRank))):
				print(" \nYou can play the suit " + Card.suits[player.findMatching(inputRank)[j]] + " (" + str(player.findMatching(inputRank)[j]) + ")")
			
			print(" \nSuit:")
			inputSuit = input()
			
			player.discard(inputSuit,inputRank)
			player.checkCombo()
			
			if(inputRank == 5):
				game.trickPoints += 5
			elif(inputRank == 10):
				game.trickPoints += 10
			elif(inputRank == 13):
				game.trickPoints += 10
			elif(inputRank == 15):
				game.trickPoints -= 25
			elif(inputRank == 16):
				game.trickPoints += 25
		
		# They want to play a pair:
		elif(game.currComb == 1):		
			print(" \nPair rank:")
			inputRank = input()
			
			game.currCard = inputRank
			
			if(len(player.findMatching(inputRank)) == 2):
				player.discard(player.findMatching(inputRank)[0],inputRank)
				player.discard(player.findMatching(inputRank)[1],inputRank)
				player.checkCombo()
				
			elif(len(player.findMatching(inputRank)) > 2):
				# ask for suits
				print(" \nPossible suits, choose two of the following:")
				for j in range(len(player.findMatching(inputRank))):
					print(player.findMatching(inputRank)[j])
				inputSuit1 = input()
				inputSuit2 = input()
				
				player.discard(inputSuit1,inputRank)
				player.discard(inputSuit2,inputRank)
				player.checkCombo()
				
			player.checkCombo()
			
			if(inputRank == 5):
				game.trickPoints += 2*5
			elif(inputRank == 10):
				game.trickPoints += 2*10
			elif(inputRank == 13):
				game.trickPoints += 2*10
			
			else:
				print("Error. You cannot play this pair.")			
			
		# They want to play a triple:
		elif(game.currComb == 2):
			print(" \nTriple rank:")
			inputRank = input()
			
			game.CurrCard = inputRank
			
			if(len(player.findMatching(inputRank)) == 3):
				player.discard(player.findMatching(inputRank)[0],inputRank)
				player.discard(player.findMatching(inputRank)[1],inputRank)
				player.discard(player.findMatching(inputRank)[2],inputRank)
				player.checkCombo()
			
			elif(len(player.findMatching(inputRank)) > 3):
				# ask for suits
				print(" \nPossible suits, choose three of the following (attention, you are splitting a bomb):")
				for j in range(len(player.findMatching(inputRank))):
					print(player.findMatching(inputRank)[j])
				inputSuit1 = input()
				inputSuit2 = input()
				inputSuit3 = input()
				
				player.discard(inputSuit1,inputRank)
				player.discard(inputSuit2,inputRank)
				player.discard(inputSuit3,inputRank)
				player.checkCombo()
			
			if(inputRank == 5):
				game.trickPoints += 3*5
			elif(inputRank == 10):
				game.trickPoints += 3*10
			elif(inputRank == 13):
				game.trickPoints += 3*10
				
		# They want to play a full house (if phoenix is in game: pair is "kicker")
		elif(game.currComb == 3):
			print(" \nFull house code:")
			inputCode = input()
			
			game.currCard = inputCode
			
			if(len(player.findMatching(player.getFullHouse(inputCode)[0])) == 3 and len(player.findMatching(player.getFullHouse(inputCode)[1])) == 2):
				for i in range(3):
					player.discard(player.findMatching(player.getFullHouse(inputCode)[0])[i],player.getFullHouse(inputCode)[0])
				for j in range(2):
					player.discard(player.findMatching(player.getFullHouse(inputCode)[1])[j],player.getFullHouse(inputCode)[1])
				player.checkCombo()
			elif(len(player.findMatching(player.getFullHouse(inputCode)[0])) == 3 and len(player.findMatching(player.getFullHouse(inputCode)[1])) == 3):
				print("You're splitting a triple. Which cards do you want to play?")
				print("You can play the suit:")
				for l in range(3):
					print(player.findMatching(player.getFullHouse(inputCode)[1])[l])
					player.discard(player.findMatching(player.getFullHouse(inputCode)[0])[l],player.getFullHouse(inputCode)[0])
				inputSuit1 = input()
				inputSuit2 = input()
				player.discard(inputSuit1,player.getFullHouse(inputCode)[1])
				player.discard(inputSuit2,player.getFullHouse(inputCode)[1])
				player.checkCombo()
			elif(len(player.findMatching(player.getFullHouse(inputCode)[0])) == 3 and len(player.findMatching(player.getFullHouse(inputCode)[1])) == 4):
				print("You're splitting a triple. Which cards do you want to play?")
				print("You can play the suit:")
				for l in range(4):
					print(player.findMatching(player.getFullHouse(inputCode)[1])[l])
					if l < 3:
						player.discard(player.findMatching(player.getFullHouse(inputCode)[0])[l],player.getFullHouse(inputCode)[0])
				inputSuit1 = input()
				inputSuit2 = input()
				player.discard(inputSuit1,player.getFullHouse(inputCode)[1])
				player.discard(inputSuit2,player.getFullHouse(inputCode)[1])
				player.checkCombo()
			elif(len(player.findMatching(player.getFullHouse(inputCode)[0])) == 4 and len(player.findMatching(player.getFullHouse(inputCode)[1])) == 2):
				print("You're splitting a bomb. Which cards do you want to play?")
				print("You can play the suit:")
				for l in range(4):
					print(player.findMatching(player.getFullHouse(inputCode)[0])[l])
					if l < 2:
						player.discard(player.findMatching(player.getFullHouse(inputCode)[1])[l],player.getFullHouse(inputCode)[1])
				inputSuit1 = input()
				inputSuit2 = input()
				player.discard(inputSuit1,player.getFullHouse(inputCode)[0])
				player.discard(inputSuit2,player.getFullHouse(inputCode)[0])
				player.checkCombo()
			elif(len(player.findMatching(player.getFullHouse(inputCode)[0])) == 4 and len(player.findMatching(player.getFullHouse(inputCode)[1])) == 3):
				print("You're splitting bomb and triple. Which cards do you play?")
				print("For triple, you can play the suits:")
				for l in range(4):
					print(player.findMatching(player.getFullHouse(inputCode)[0])[l])
				inputSuit1 = input()
				inputSuit2 = input()
				inputSuit3 = input()
				player.discard(inputSuit1,player.getFullHouse(inputCode)[0])
				player.discard(inputSuit2,player.getFullHouse(inputCode)[0])
				player.discard(inputSuit3,player.getFullHouse(inputCode)[0])
				print("For pair, you can play the suits:")
				for l in range(3):
					print(player.findMatching(player.getFullHouse(inputCode)[1])[l])
				inputSuit1 = input()
				inputSuit2 = input()
				player.discard(inputSuit1,player.getFullHouse(inputCode)[1])
				player.discard(inputSuit2,player.getFullHouse(inputCode)[1]) 
				player.checkCombo()
			elif(len(player.findMatching(player.getFullHouse(inputCode)[0])) == 4 and len(player.findMatching(player.getFullHouse(inputCode)[1])) == 4):
				print("You're splitting bomb and triple. Which cards do you play?")
				print("For triple, you can play the suits:")
				for l in range(4):
					print(player.findMatching(player.getFullHouse(inputCode)[0])[l])
				inputSuit1 = input()
				inputSuit2 = input()
				inputSuit3 = input()
				player.discard(inputSuit1,player.getFullHouse(inputCode)[0])
				player.discard(inputSuit2,player.getFullHouse(inputCode)[0])
				player.discard(inputSuit3,player.getFullHouse(inputCode)[0])
				print("For pair, you can play the suits:")
				for l in range(4):
					print(player.findMatching(player.getFullHouse(inputCode)[1])[l])
				inputSuit1 = input()
				inputSuit2 = input()
				player.discard(inputSuit1,player.getFullHouse(inputCode)[1])
				player.discard(inputSuit2,player.getFullHouse(inputCode)[1]) 
				player.checkCombo()
			else:
				print("Something went wrong with full houses.")

			if(player.getFullHouse(inputCode)[0] == 5):
				game.trickPoints += 3*5
			elif(player.getFullHouse(inputCode)[0] == 10):
				game.trickPoints += 3*10
			elif(player.getFullHouse(inputCode)[0] == 13):
				game.trickPoints += 3*10
			if(player.getFullHouse(inputCode)[1] == 5):
				game.trickPoints += 2*5
			elif(player.getFullHouse(inputCode)[1] == 10):
				game.trickPoints += 2*10
			elif(player.getFullHouse(inputCode)[1] == 13):
				game.trickPoints += 2*10

		# They want to play n connected pairs
		elif(game.currComb == 4):
			print(" \nConnected pairs code:")
			inputCode = input()
			
			game.currCard = inputCode
			
			arrayMoreThanTwo = []
			
			for i in range( player.findMatching(player.getConnectedPairs(inputCode)[0]),  player.findMatching(player.getConnectedPairs(inputCode)[1]) + 1 ):
				if(len()
			
			else:
				if(len(player.findMatching(player.getConnectedPairs(inputCode)[0])) > 2):
					for i in range(3):
						player.discard(player.findMatching(player.getFullHouse(inputCode)[0])[i],player.getFullHouse(inputCode)[0])
					for j in range(2):
						player.discard(player.findMatching(player.getFullHouse(inputCode)[1])[j],player.getFullHouse(inputCode)[1])
				player.checkCombo()
		
		# They want to play a straight
		elif(game.currComb == 5):
			dd
						
		player.possibleActions = 3
		
		game.passedCounter = 0
		
		game.currLead = player.number - 1
		
		# ~ if(len(player.hand) == 0):
			# ~ game.activePlayers -= 1
			# ~ player.active = False
			
	# Current player can bet or fold
	elif(player.possibleActions == 1):
		print(" \nDou you want to play (0) or pass (1)?")
		#player.checkPossibleCombos()
		callOption = input()
		
		if callOption == 0:
			print(" \nYou can play the following combinations.")
			j = 0
			while j < len(player.combo[game.currComb][:]):
				if(game.currComb <= 2):
					if player.combo[game.currComb][j] > 0 and j > game.currCard:
						if(game.currComb == 0):
							print(Card.ranks[j]) # works only for single card
						else:
							print(Card.ranks[j+2])
				elif(game.currComb == 3):
					if player.combo[game.currComb][j] > 0 and player.getFullHouse(j)[0] > player.getFullHouse(game.currCard)[0]:
						print("three of " + Card.ranks[player.getFullHouse(j)[0]] + ", two of " + Card.ranks[player.getFullHouse(j)[1]] + "(" + str(j) + ")")
				
				j += 1
			
			if(game.currComb == 0): # single card
				inputRank = input()
				
				game.currCard = inputRank
				
				for j in range(len(player.findMatching(inputRank))):
					print(" \nYou can play the suit " + Card.suits[player.findMatching(inputRank)[j]] + " (" + str(player.findMatching(inputRank)[j]) + ")")
				
				print(" \nSuit:")
				inputSuit = input()
				
				player.discard(inputSuit,inputRank)
				player.checkCombo()
				
				if(inputRank == 5):
					game.trickPoints += 5
				elif(inputRank == 10):
					game.trickPoints += 10
				elif(inputRank == 13):
					game.trickPoints += 10
				elif(inputRank == 15):
					game.trickPoints -= 25
				elif(inputRank == 16):
					game.trickPoints += 25					
				
			elif(game.currComb == 1): # pair
				inputRank = input()
				
				game.currCard = inputRank
				
				if(len(player.findMatching(inputRank)) == 2):
					for l in range(2):
						player.discard(player.findMatching(inputRank)[l],inputRank)
					player.checkCombo()
				elif(len(player.findMatching(inputRank)) == 3):
					print("You're spliiting a triple. Which cards do you want to play?")
					print("You can play the suit:")
					for l in range(3):
						print("You can play the suit:")
					inputSuit1 = input()
					inputSuit2 = input()
					player.discard(inputSuit1,inputRank)
					player.discard(inputSuit2,inputRank)
					player.checkCombo()
				elif(len(player.findMatching(inputRank)) == 4):
					print("You're spliiting a bomb. Which cards do you want to play?")
					print("You can play the suit:")
					for l in range(4):
						print("You can play the suit:")
					inputSuit1 = input()
					inputSuit2 = input()
					player.discard(inputSuit1,inputRank)
					player.discard(inputSuit2,inputRank)
					player.checkCombo()
				else:
					print("Something went terribly wrong. You don't have a pair, yet the program told me you have.")
					
				if(inputRank == 5):
					game.trickPoints += 2*5
				elif(inputRank == 10):
					game.trickPoints += 2*10
				elif(inputRank == 13):
					game.trickPoints += 2*10
					
			elif(game.currComb == 2): # three of a kind
				inputRank = input()
				
				game.currCard = inputRank
				
				if(len(player.findMatching(inputRank)) == 3):
					for l in range(3):
						player.discard(player.findMatching(inputRank)[l],inputRank)
					player.checkCombo()
				elif(len(player.findMatching(inputRank)) == 4):
					print("You're spliiting a bomb. Which cards do you want to play?")
					print("You can play the suit:")
					for l in range(4):
						print("You can play the suit:")
					inputSuit1 = input()
					inputSuit2 = input()
					inputSuit3 = input()
					player.discard(inputSuit1,inputRank)
					player.discard(inputSuit2,inputRank)
					player.discard(inputSuit3,inputRank)
					player.checkCombo()
				else:
					print("Something went terribly wrong. You don't have a triple, yet the program told me you have.")
					
				if(inputRank == 5):
					game.trickPoints += 3*5
				elif(inputRank == 10):
					game.trickPoints += 3*10
				elif(inputRank == 13):
					game.trickPoints += 3*10
					
			elif(game.currComb == 3): # full house
				inputRank = input()
				
				game.currCard = inputRank
				
				inputTriple = player.getFullHouse(inputRank)[0]
				inputPair = player.getFullHouse(inputRank)[1]
				
				if(len(player.findMatching(inputTriple)) == 3 and len(player.findMatching(inputPair)) == 2):
					for l in range(3):
						player.discard(player.findMatching(inputTriple)[l],inputTriple)
					for l in range(2):
						player.discard(player.findMatching(inputPair)[l],inputPair)
					player.checkCombo()
				elif(len(player.findMatching(inputTriple)) == 3 and len(player.findMatching(inputPair)) == 3):
					print("You're spliiting a triple. Which cards do you want to play?")
					print("You can play the suit:")
					for l in range(3):
						print(player.findMatching(inputPair)[l])
						player.discard(player.findMatching(inputTriple)[l],inputTriple)
					inputSuit1 = input()
					inputSuit2 = input()
					player.discard(inputSuit1,inputPair)
					player.discard(inputSuit2,inputPair)
					player.checkCombo()
				elif(len(player.findMatching(inputTriple)) == 3 and len(player.findMatching(inputPair)) == 4):
					print("You're spliiting a bomb. Which cards do you want to play?")
					print("You can play the suit:")
					for l in range(4):
						print(player.findMatching(inputPair)[l])
						if l<3:
							player.discard(player.findMatching(Triple)[l],inputTriple)
					inputSuit1 = input()
					inputSuit2 = input()
					player.discard(inputSuit1,inputPair)
					player.discard(inputSuit2,inputPair)
					player.checkCombo()
				elif(len(player.findMatching(inputTriple)) == 4 and len(player.findMatching(inputPair)) == 2):
					print("You're spliiting a bomb. Which cards do you want to play?")
					print("You can play the suit:")
					for l in range(4):
						print(player.findMatching(inpuTriple)[l])
						if l<2:
							player.discard(player.findMatching(inputPair)[l],inputPair)
					inputSuit1 = input()
					inputSuit2 = input()
					inputSuit3 = input()
					player.discard(inputSuit1,inputTriple)
					player.discard(inputSuit2,inputTriple)
					player.discard(inputSuit3,inputTriple)
					player.checkCombo()
				elif(len(player.findMatching(inputTriple)) == 4 and len(player.findMatching(inputPair)) == 3):
					print("You're splitting bomb and triple. Which cards do you play?")
					print("For triple, you can play the suits:")
					for l in range(4):
						print(player.findMatching(inpuTriple)[l])
					inputSuit1 = input()
					inputSuit2 = input()
					inputSuit3 = input()
					player.discard(inputSuit1,inputTriple)
					player.discard(inputSuit2,inputTriple)
					player.discard(inputSuit3,inputTriple)
					print("For pair, you can play the suits:")
					for l in range(3):
						print(player.findMatching(inputPair)[l])
					inputSuit1 = input()
					inputSuit2 = input()
					player.discard(inputSuit1,inputPair)
					player.discard(inputSuit2,inputPair) 
					player.checkCombo()
				elif(len(player.findMatching(inputTriple)) == 4 and len(player.findMatching(inputPair)) == 4):
					print("You're splitting two bombs. Which cards do you play?")
					print("For triple, you can play the suits:")
					for l in range(4):
						print(player.findMatching(inpuTriple)[l])
					inputSuit1 = input()
					inputSuit2 = input()
					inputSuit3 = input()
					player.discard(inputSuit1,inputTriple)
					player.discard(inputSuit2,inputTriple)
					player.discard(inputSuit3,inputTriple)
					print("For pair, you can play the suits:")
					for l in range(4):
						print(player.findMatching(inputPair)[l])
					inputSuit1 = input()
					inputSuit2 = input()
					player.discard(inputSuit1,inputPair)
					player.discard(inputSuit2,inputPair) 
					player.checkCombo()
				else:
					print("Something went wrong with full houses.")
					
				if(inputTriple == 5):
					game.trickPoints += 3*5
				elif(inputTriple == 10):
					game.trickPoints += 3*10
				elif(inputTriple == 13):
					game.trickPoints += 3*10
				if(inputPair == 5):
					game.trickPoints += 2*5
				elif(inputPair == 10):
					game.trickPoints += 2*10
				elif(inputPair == 13):
					game.trickPoints += 2*10

			elif(game.currComb == 4): # n connected pairs
				print(2)
				
			elif(game.currComb == 5): # straight
				print(2)
			
			player.possibleActions = 3
			
			game.passedCounter = 0
			game.currLead = player.number - 1
			
			# ~ if(len(player.hand) == 0):
				# ~ game.activePlayers -= 1
				# ~ player.active = False
				# ~ game.passedCounter = -1
			
		elif callOption == 1:
			print("Thank you. Next player's turn.")
						
			player.possibleActions = 3
			
			game.passedCounter += 1
			
		else:
			print("Error.")

	# Current player can only fold
	elif(player.possibleActions == 2):
		print(" \nYou cannot go higher.")
		player.possibleActions = 3
		game.passedCounter += 1
		input()
		
	if(len(player.hand) == 0):
		game.activePlayers -= 1
		player.active = False
		#
		# ~ game.passedCounter = -game.activePlayers
		
		# ~ game.leadPlayer = game.findActivePlayer(game.currPlayer-1)
			

	
	# ~ print(" \nRank:")

	
	# ~ print(player.findMatching(inputRank))
	
	# ~ print(" \nSuits:")
	# ~ inputSuits = input()
	# ~ player.discard(inputSuits,inputRank)
	# ~ player.checkCombo()
	
	
	
	
	
	
	print("No of cards after move is " + str(len(player.hand)))
	

###########################################################################################
# MAIN function
###########################################################################################
def main():
	# game ends when one team has reached so and so many pointds
	points_threshold = 200
	
	# ~ # Initialize the deck
	# ~ deck = Deck()
	
	# Initialize the players
	player1 = Player("Bernadette",1,1)
	player2 = Player("Manuel (Bot)",2,2)
	player3 = Player("Johannes (Bot)",3,1)
	player4 = Player("Freia (Bot)",4,2)
	players = [player1,player2,player3,player4]
	
	# Initialize the game
	game = Round(0,0,players)
	
	round_num = 0
	
	while(game.points1 < points_threshold and game.points2 < points_threshold):
	
		# Initialize the deck
		deck = Deck()
	
		# Distribute the cards
		for i in range(14):
			player1.draw(deck)
			player2.draw(deck)
			player3.draw(deck)
			player4.draw(deck)
			
		turn = 0
		
		game.currPlayer = round_num%4
		players[game.currPlayer].possibleActions = 0
		
		while((len(player1.hand)>0 and len(player2.hand)>0) or
		(len(player1.hand)>0 and len(player4.hand)>0) or
		(len(player3.hand)>0 and len(player2.hand)>0) or
		(len(player3.hand)>0 and len(player4.hand)>0)):
			if(len(players[game.currPlayer].hand)>0):
				
				print("active players: " +str(game.activePlayers))
				print("passed: " +str(game.passedCounter))
				print("Points Bernadette: " + str(player1.points))
				print("Points Manuel: " + str(player2.points))
				print("Points Johannes: " + str(player3.points))
				print("Points Freia: " + str(player4.points))

				startTurn(players[game.currPlayer],game)
				
				# if nobody plays, distribute points and start fresh
				if(game.passedCounter == game.activePlayers - 1 and len(players[game.currLead].hand) > 0 or game.passedCounter == game.activePlayers and len(players[game.currLead].hand) == 0 ):
					print("Alle passen.")
					game.earnCards(players[game.currLead])
					game.passedCounter = 0
					if(len(players[game.currLead].hand) == 0):
						game.currPlayer = game.findActivePlayer(game.currLead) # currLead
						players[game.currPlayer].possibleActions = 0
					else:
						# set leadPlayer to player who last came out
						game.leadPlayer = game.currLead
						# ~ game.currPlayer = game.findActivePlayer(game.leadPlayer)
						game.currPlayer = game.leadPlayer
						players[game.currPlayer].possibleActions = 0
					
				
				# update what options the next player has (exception will be Dog)
				elif(game.currComb != 7):
					game.currPlayer = game.nextActivePlayer()
					players[game.currPlayer].checkPossibleCombos(False)
					j = 0
					players[game.currPlayer].possibleActions = 2
					while j < len(players[game.currPlayer].combo[game.currComb][:]):
						if(game.currComb <= 2):
							if players[game.currPlayer].combo[game.currComb][j] > 0 and j > game.currCard:
								players[game.currPlayer].possibleActions = 1
						elif(game.currComb == 3):
							if players[game.currPlayer].combo[game.currComb][j] > 0 and players[game.currPlayer].getFullHouse(j) > players[game.currPlayer].getFullHouse(game.currCard):
								players[game.currPlayer].possibleActions = 1
						j += 1
						
				else:
					print("Implement the Dog.")
		
		round_num += 1
		
		print("Game over.")
			
	
###########################################################################################
# call MAIN function
###########################################################################################	
main()
