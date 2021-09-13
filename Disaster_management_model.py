import agentpy as ap
import numpy as np
import pandas as pd
import random
import networkx as nx
import matplotlib.pyplot as plt

class data_source(object):
    # 27 municipalities
    def __init__(self):
        # import network data, create dict by municipalities
        self.df = pd.read_csv('data_source/network_index.csv')
        self.city = list(set(self.df['City']))
        self.municipalities = {}
        for i in self.city:
            self.municipalities[i] = list(self.df.loc[(self.df.City == i),'No'])
        self.dict_keys = sorted(list(self.municipalities.keys()))
        #disaster percentage by month
        self.df2 = pd.read_csv('data_source/disaster_by_month_pct.csv',index_col=False)
        self.df2.set_index(['Month'],inplace = True)
        self.disaster_m_p = self.df2.values.tolist()
        #average disaster number per day by month
        self.disaster_pd = [4.967741935,
9.342857143,
6.567741935,
4.653333333,
2.322580645,
2,
1.793548387,
2.393548387,
4.113333333,
5.490322581,
5.713333333,
5.587096774]

    def get_districts(self,index):
        # return districts list by municipality name
        return self.dict_keys[index-1], self.municipalities[self.dict_keys[index-1]]
    
    def get_average_disaster(self,month):
        return self.disaster_pd[month]
    
    def get_month(self,t):
        if t in range(32):
            return 0
        elif t in range(60):
            return 1
        elif t in range(91):
            return 2
        elif t in range(121):
            return 3
        elif t in range(152):
            return 4
        elif t in range(182):
            return 5
        elif t in range(213):
            return 6
        elif t in range(244):
            return 7
        elif t in range(274):
            return 8
        elif t in range(305):
            return 9
        elif t in range(335):
            return 10
        else:
            return 11
    
    def get_disaster_pct(self,month):
        return self.disaster_m_p[month]
    
    def get_info(self):
        return self.dict_keys

            
class Municipality(ap.Agent):
    
    def setup(self):
        # get disticts dict
        self.source = data_source()
        self.name, self.districts = self.source.get_districts(self.id)
        #average affected districts number by disaster types
        self.districts_number_by_dtype = {
            'Earthquake': 1.11,
            'Fire': 1.13,
            'Flood': 1.78,
            'Landslide': 1.36,
            'Tornado': 1.3
        }
        
    def disaster(self,d_type,refugees_number):
        self.k = max(1,np.random.poisson(self.districts_number_by_dtype[d_type])) #generate affected districts amount
        self.affected_districts = []
        self.affected_districts.append(np.random.choice(self.districts))
        while len(self.affected_districts) < self.k:
            self.affected_districts.append(np.random.choice(list(self.model.G.neighbors(np.random.choice(self.affected_districts)))))
            self.affected_districts = list(set(self.affected_districts))
        self.refugees_number = []
        for i in self.affected_districts:
            self.refugees_number.append(round(refugees_number/self.k))
    
    
class DisasterModel(ap.Model):
    
    def setup(self):
        self.source = data_source()
        self.agents = ap.AgentList(self, self.p.agents, Municipality)
        self.types_list = ['Landslide','Fire','Tornado','Flood','Earthquake'] #disaster types
        #import disaster by cities pct
        self.dbc_df = pd.read_csv('data_source/disaster_by_cities_pct.csv')
        self.dbc_dict = {}
        for i in range(len(self.dbc_df)):
            source = self.dbc_df.iloc[i].values.tolist()
            self.dbc_dict[source[0]] = source[1:]
            
        #setup network
        self.G = nx.Graph()
        self.network = np.load('data_source/edges&warehouses.npy',allow_pickle=True).item()
        self.G.add_nodes_from(self.network['nodes'])
        self.G.add_edges_from(self.network['edges'])
        for i in self.network['warehouses'].keys():
                self.G.nodes[i]['capacity'] = self.network['warehouses'][i]
            
        #refugess number by disaster & cities
        self.rfg_by_dnc = np.load('data_source/refugees_number_by_disaster&cities.npy',allow_pickle=True).item()

    def step(self):
        
        def generate_disaster():
            self.day_report = {}
            self.month = self.source.get_month(self.model.t)
            self.disaster_number = np.random.poisson(self.source.get_average_disaster(self.month)*1.2) #generate disaster number
            for disaster in range(self.disaster_number): #generate data for each disaster
                self.disaster_type = np.random.choice(self.types_list,p=self.source.get_disaster_pct(self.month)) # generate disaster type base on month
                self.affected_cities_number = 1 #number of cities being affected
                self.affected_cities = []
                for i in range(self.affected_cities_number):
                    self.affected_cities.append(np.random.choice(range(1,self.p.agents+1),p=self.dbc_dict[self.disaster_type]))
                for city in self.affected_cities:
                    self.target =  self.agents.select(self.agents.id == city)
                    try:
#                         self.refugees_number = round(np.random.triangular(*self.rfg_by_dnc[self.disaster_type][city]))
                        self.refugees_number = np.random.poisson(self.rfg_by_dnc[self.disaster_type][city][1])
                    except ValueError:
                        self.refugees_number = 0
                    self.target.disaster(self.disaster_type,self.refugees_number) # call the selected city to generate disaster 
                    for d in range(len(self.target.affected_districts[0])):
                        self.day_report[self.target.affected_districts[0][d]] = self.target.refugees_number[0][d]
                        #report in district level
                        result_sp.append([year,self.t,self.month+1,self.target.name[0],self.target.affected_districts[0][d],self.disaster_type,self.target.refugees_number[0][d]])
                    #report in municipality level
                    result.append([year,self.t,self.month+1,self.target.name[0],self.target.affected_districts[0],self.disaster_type,self.refugees_number])
                    
        def food_distribution():
            self.task = {}
            for district in self.day_report.keys():
                if self.day_report[district] > 0:
                    t = 0
                    warehouse = self.G.nodes[district]['nearest warehouse'][t]
                    while self.G.nodes[district]['nearest warehouse'][t] in self.day_report.keys(): #if the warehouse is affected, then select the next nearest one
                        t+=1
                        warehouse = self.G.nodes[district]['nearest warehouse'][t]
                    if warehouse not in self.task:
                        self.task[warehouse] = [district]
                    else:
                        self.task[warehouse] += [district]
            for i in self.task.keys():
                self.task[i] = sorted(self.task[i], key = lambda x:nx.shortest_path_length(self.G,i,x,weight = 'length'))
                
            for i in self.task.keys():
                self.distance = 0
                self.food = 0
                task = [i] + self.task[i]
                for d in range(1,len(task)):
                    self.distance += nx.shortest_path_length(self.G,task[d-1],task[d],weight = 'length')
                    self.food += self.day_report[task[d]]
                kpi.append([year,self.model.t,round(self.distance),self.food,round(self.distance/80,2),round(self.distance/60,2),round(self.distance/40,2)])
                    
        generate_disaster()
        food_distribution()
        
    def update(self):
        pass
        
    def end(self):
        pass


if __name__ == '__main__':
    result = [['Year','Day','Month','Municipality','District','Disaster','Refugees number']]
    result_sp = [['Year','Day','Month','Municipality','District','Disaster','Refugees number']]
    kpi = [['Year','Day','distance','food','delivered time at 80km/h','delivered time at 60km/h','delivered time at 40km/h']]


    parameters = {  
        'agents': 27,
        'steps':365
    }

    for i in range(1):
        year = i+1
        model = DisasterModel(parameters)
        model.run()
        
    pd.DataFrame(kpi[1:],columns=kpi[0]).to_csv('model_output/kpi.csv', index=False)
    pd.DataFrame(result[1:],columns=result[0]).to_csv('model_output/disaster_report.csv', index=False)
    pd.DataFrame(result_sp[1:],columns=result_sp[0]).to_csv('model_output/disaster_report_sp.csv', index=False)