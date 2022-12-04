#! /usr/bin/env python
# -*- coding:utf-8 -*-

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.python.keras.layers import Dropout, Dense, GRU
import matplotlib.pyplot as plt
import os
import pandas as pd
import talib as ta
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
import math

# 读取股票文件
stock='000009.SZ'
close_df = pd.read_csv(r"C:\Users\Jiwei Tu\Desktop\深度学习预测\中证500\中证500\handledData\T_close.csv")
high_df = pd.read_csv(r"C:\Users\Jiwei Tu\Desktop\深度学习预测\中证500\中证500\handledData\T_high.csv")
low_df = pd.read_csv(r"C:\Users\Jiwei Tu\Desktop\深度学习预测\中证500\中证500\handledData\T_low.csv")
pct_df = pd.read_csv(r"C:\Users\Jiwei Tu\Desktop\深度学习预测\中证500\中证500\handledData\T_pct.csv")
volume_df = pd.read_csv(r"C:\Users\Jiwei Tu\Desktop\深度学习预测\中证500\中证500\handledData\T_volume.csv")

#参数设置
test_amount = 88
GRU_timestep = 20
feature_numbers = 6
theta = 0.005

def generate_feature():
    feature = pct_df[['TRADE_DT']]
    close = close_df[stock].values
    high = high_df[stock].values
    low = low_df[stock].values
    pct = pct_df[stock].values
    volume = volume_df[stock]
    trange_2 = ta.TRANGE(high,low, close)
    rsi_5 = ta.RSI(close, timeperiod=5)
    willer_14 = ta.WILLR(high, low, close, timeperiod=14)
    cci_14= ta.CCI(high, low, close, timeperiod=14)
    rocp_5 = ta.ROCP(close, timeperiod=5)
    MACD_macd,MACD_macdsignal,MACD_macdhist = ta.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    feature['trange_2'] = trange_2
    feature['rsi_5'] = rsi_5
    feature['willer_14'] = willer_14
    feature['cci_14'] = cci_14
    feature['rocp_5'] = rocp_5
    feature['MACD_macd'] = MACD_macd
    feature['pct_chg'] = pct
    return feature

def create_dataset(data,n_predictions,n_next,target_index=6):
    '''
    对数据进行处理
    '''
    dim = data.shape[1]
    train_X, train_Y = [], []
    for i in range(data.shape[0]-n_predictions-n_next-1):
        a = data[i:(i+n_predictions),0:target_index]
        train_X.append(a)
        tempb = data[(i+n_predictions):(i+n_predictions+n_next),target_index]
        b = []
        for j in range(len(tempb)):
            b.append(tempb[j])
        train_Y.append(b)
    train_X = np.array(train_X,dtype='float64')
    train_Y = np.array(train_Y,dtype='float64')
    return train_X, train_Y

def map_func(x,theta):
        if x > theta:
            return 1
        elif x < -1*theta:
            return -1 
        else:
            return -1

stock_pd = generate_feature()
stock_pd.dropna(how = 'any',axis= 0,inplace=True)#缺失值的行全部剔除并成为新的dataframe
stock_pd.to_csv(r"C:\Users\Jiwei Tu\Desktop\stock_pd.csv",encoding="utf_8_sig")
stock_lenth = stock_pd.shape[0]
# 前(1219-test_amount=919)天的六个指标与跌涨幅作为训练集
training_set = stock_pd.iloc[426:732 - test_amount, 1:8].values
test_set = stock_pd.iloc[732 - test_amount:734, 1:8].values

# 归一化，求得训练集的最大值，最小值这些训练集固有的属性，并在训练集上进行归一化，利用训练集的属性对测试集进行归一化
x_train_set = training_set[:,0:6]
y_train_set = training_set[:,6]
x_test_set = test_set[:,0:6]
y_test_set = test_set[:,6]

sc1 = MinMaxScaler(feature_range=(0, 1)) 
x_train_set = sc1.fit_transform(x_train_set)
x_test_set = sc1.transform(x_test_set)

sc2 = MinMaxScaler(feature_range=(0, 1)) 
y_train_set = sc2.fit_transform(y_train_set.reshape(-1,1))
y_test_set = sc2.transform(y_test_set.reshape(-1,1))

training_set = np.hstack((x_train_set,y_train_set))
test_set = np.hstack((x_test_set,y_test_set))

x_train = []
y_train = [] 

x_test = []
y_test = []

x_train,y_train = create_dataset(training_set,GRU_timestep,1)
x_test,y_test = create_dataset(test_set,GRU_timestep,1)

# 打乱训练集数据，每次打乱前seed一下确保两次产生随机数相同
np.random.seed(7)
np.random.shuffle(x_train)
np.random.seed(7)
np.random.shuffle(y_train)
tf.random.set_seed(7)
 
# 使训练集和测试集符合RNN输入要求：[送入样本数， 循环核时间展开步数， 每个时间步输入特征个数]。
# 此处整个数据集送入，送入样本数为x_train.shape[0]即2066组数据；输入GRU_timestep个开盘价，预测出第61天的开盘价，循环核时间展开步数为GRU_timestep;
x_train = np.reshape(x_train, (x_train.shape[0], GRU_timestep, feature_numbers))
x_test = np.reshape(x_test, [x_test.shape[0], GRU_timestep, feature_numbers])
 
# 搭建神经网络
model = tf.keras.Sequential([
    GRU(300, return_sequences=True),  # 记忆体个数，return_sequences=True，循环核各时刻会把ht推送到下一层
    Dropout(0.2),
    GRU(150),  #仅最后时间步输出ht
    Dropout(0.2),
    Dense(1)
])

# 配置训练方法
model.compile(
    optimizer=tf.keras.optimizers.Adam(0.001),
    loss='mean_squared_error',  # 损失函数用均方误差
    metrics=['mae','mse'])
# 该应用只观测loss数值，不观测准确率，所以删去metrics选项，一会在每个epoch迭代显示时只显示loss值
 
# 保存模型
checkpoint_path_save = './checkpoint/gru_stock.ckpt'
 
# 如果模型存在，就加载模型
if os.path.exists(checkpoint_path_save + '.index'):
    print('--------------------load the model----------------------')
    # 加载模型
    model.load_weights(checkpoint_path_save)
 
# 保存模型，借助tensorflow给出的回调函数，直接保存参数和网络
'''
 注： monitor 配合 save_best_only 可以保存最优模型，
 包括：训练损失最小模型、测试损失最小模型、训练准确率最高模型、测试准确率最高模型等。
'''
cp_callback = tf.keras.callbacks.ModelCheckpoint(
    filepath=checkpoint_path_save,
    save_weights_only=True,
    save_best_only=True,
    monitor='val_loss'
)
 
# 模型训练
history = model.fit(x_train, y_train,
                    batch_size=32, epochs=10, validation_data=(x_test, y_test),
                    validation_freq=1, callbacks=[cp_callback])
 
# 统计网络结构参数
model.summary()
 
# 参数提取，写至weights_stock.txt文件中
file = open('./gru_weights_stock.txt', 'w')
for v in model.trainable_variables:
    file.write(str(v.name) + '\n')
    file.write(str(v.shape) + '\n')
    file.write(str(v.numpy()) + '\n')
file.close()
 
# 获取loss
loss = history.history['loss']
val_loss = history.history['val_loss']
 
# 绘制loss
plt.plot(loss, label='Training Loss')
plt.plot(val_loss, label='Validation Loss')
plt.title('Training and Validation Loss')
plt.legend()
plt.show()
 
######################## predict ###################################
 
# 测试集输入到模型中进行预测
predicted_stock_price_1 = model.predict(x_test)

# 对预测与真实数据还原---从(0, 1)反归一化到原始范围
predicted_stock_price = sc2.inverse_transform(predicted_stock_price_1)
real_stock_price = sc2.inverse_transform(y_test)

result = predicted_stock_price.flatten()
print(result)
# 画出真实数据和预测数据的对比曲线
plt.plot(real_stock_price, color='red', label='Real Percent Change')
plt.plot(predicted_stock_price, color='blue', label='Predicted Percent Change')
plt.title('Percent Change Prediction')
plt.xlabel('Time')
plt.ylabel('Percent Change')
plt.legend()
plt.show()
 
###################### evluate ######################
# calculate MSE 均方误差 ---> E[(预测值-真实值)^2] (预测值减真实值求平方后求均值)
mse = mean_squared_error(predicted_stock_price, real_stock_price)
# calculate RMSE 均方根误差--->sqrt[MSE]    (对均方误差开方)
rmse = math.sqrt(mean_squared_error(predicted_stock_price, real_stock_price))
# calculate MAE 平均绝对误差----->E[|预测值-真实值|](预测值减真实值求绝对值后求均值）
mae = mean_absolute_error(predicted_stock_price, real_stock_price)

predicted_stock_price = pd.DataFrame(predicted_stock_price)
predicted_stock_price.to_csv(r"C:\Users\Jiwei Tu\Desktop\single_predict_df.csv",encoding="utf_8_sig")
real_stock_price = pd.DataFrame(real_stock_price)
real_stock_price.to_csv(r"C:\Users\Jiwei Tu\Desktop\single_real_df.csv",encoding="utf_8_sig")
predicted_stock_price = predicted_stock_price.applymap(lambda x: map_func(x,theta))
predicted_stock_price.to_csv(r"C:\Users\Jiwei Tu\Desktop\single_predict_df_01.csv",encoding="utf_8_sig")
real_stock_price = real_stock_price.applymap(lambda x: map_func(x,theta))
real_stock_price.to_csv(r"C:\Users\Jiwei Tu\Desktop\single_real_df_01.csv",encoding="utf_8_sig")
same_sum = sum((predicted_stock_price == real_stock_price).values)

print('accuracy: {:.2%}'.format(same_sum[0]/predicted_stock_price.size))
print('均方误差: %.6f' % mse)
print('均方根误差: %.6f' % rmse)
print('平均绝对误差: %.6f' % mae)