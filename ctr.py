#!/usr/bin/env python
# coding=utf-8

import mydb
import random
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
db = mydb.Mydb()

"""
    CTR计算, 分配不同的用户广告位
"""
class CTR:
    def __init__(self):
        self.LR = LogisticRegression()

    # 载入广告信息
    def loadAdInfo(self):
        name = ['click', 'ad_id', 'advertiser_id', 'price', 'ad_tag', 'user_tag', 'user_sex']
        ad_info = db.getAdInfo('all')
        dict_ad_info = dict()
        for info in ad_info:
            # ad_id对应advertise_id, adsex, adtag
            dict_ad_info[info[0]] = ['-1', info[0], info[1], info[5], info[4], 'Unknown', 'Unknown']

        pd_ad_info = pd.DataFrame(data=dict_ad_info.values(), columns=name)
        # pd_ad_info = pd_ad_info.drop(['ad_id'], axis=1)
        return pd_ad_info

    # 载入用户的标签和性别信息
    def loadUserTag(self):
        user_tag = db.getUserBehavior('all')
        dict_user_tag = dict()
        for info in user_tag:
            dict_user_tag[info[0]] = (info[1], info[2])
        return dict_user_tag

    # 载入点击信息
    def loadCTRInfo(self):
        dict_user_tag = self.loadUserTag()
        name = ['click', 'ad_id', 'advertiser_id', 'price', 'ad_tag', 'user_tag', 'user_sex']
        ctr_info = db.getCtrLog('all')
        dict_ctr_info = list()
        for info in ctr_info:
            click = '1' if int(info[0])>0 else '0'
            ad_id = info[1]
            advertiser_id = info[3]
            price = info[4]
            ad_tag = info[5]
            uid = info[8]
            # if uid not in dict_user_tag:
            #     continue
            tag, sex = dict_user_tag[uid]
            dict_ctr_info.append([click, ad_id, advertiser_id, price, ad_tag, tag, sex])
        pd_ctr_info = pd.DataFrame(data=dict_ctr_info, columns=name)
        # print pd_ctr_info
        return pd_ctr_info

    # 特征工程,主要是把一个离散特征分解成多个不同的特征
    def featureEngineer(self, f):
        # 目前保留特征有:价格, 广告标签, 用户标签, 用户性别
        price = pd.get_dummies(f["price"])
        price = price.rename(columns=lambda kk:'price_'+str(kk))
        f = pd.concat([f, price], axis=1)

        ad_tag = pd.get_dummies(f['ad_tag'])
        ad_tag = ad_tag.rename(columns=lambda kk:'adtag_'+str(kk))
        f = pd.concat([f, ad_tag], axis=1)

        user_tag = pd.get_dummies(f['user_tag'])
        user_tag = user_tag.rename(columns=lambda kk:'usertag_'+str(kk))
        f = pd.concat([f, user_tag], axis=1)

        user_sex = pd.get_dummies(f['user_sex'])
        user_sex = user_sex.rename(columns=lambda kk:'usersex_'+str(kk))
        f = pd.concat([f, user_sex], axis=1)

        f = f.drop(['ad_id', 'advertiser_id', 'price', 'ad_tag', 'user_tag', 'user_sex'], axis=1)
        # print f
        return f

    # 模型训练
    def fit_model(self, f):
        f = self.featureEngineer(f)
        Y = f["click"]
        X = f.drop(['click'], axis=1)
        self.LR.fit(X, Y)

    # 预测函数, 对所有商品进行预测,给出三个概率:-1(未出现),0(出现但是没点击),1(点击过)
    def predict(self, f, train_set):
        f_size = len(f)
        # print f
        f = self.featureEngineer(pd.concat([f, train_set], axis=0))
        f = f.drop(['click'], axis=1)
        f = f[:f_size]
        # print f
        prob = self.LR.predict_proba(f)
        return prob

    # 总的函数,对ctr进行计算
    def userBehaviorCTR(self):
        pd_ad_info = self.loadAdInfo()
        pd_ctr_info = self.loadCTRInfo()
        new_concat_info = pd.concat([pd_ad_info, pd_ctr_info], axis=0)
        self.fit_model(new_concat_info)

        user_behaviors = set(db.getUserBehavior('allbehave'))
        name = ['click', 'ad_id', 'advertiser_id', 'price', 'ad_tag', 'user_tag', 'user_sex']

        ad_list = pd_ad_info["ad_id"].tolist()
        id_to_tag = dict(zip(pd_ad_info["ad_id"].tolist(), pd_ad_info["ad_tag"].tolist()))
        for user_tag, user_sex in user_behaviors:
            ad_feature = list()
            for ad_id in pd_ad_info["ad_id"]:
                details = pd_ad_info.ix[pd_ad_info.ad_id==ad_id]
                advertiser_id =  details['advertiser_id'].values[0]
                # print advertiser_id
                price = details['price'].values[0]
                ad_tag = details['ad_tag'].values[0]
                feature = ['0', ad_id, advertiser_id, price, ad_tag, user_tag, user_sex]
                ad_feature.append(feature)
            # print ad_feature
            pd_ad_feature = pd.DataFrame(data=ad_feature, columns=name)
            prob = self.predict(pd_ad_feature, new_concat_info)
            prob_list = list()
            for each in prob:
                p_of_click = each[2] # 点击概率
                prob_list.append(p_of_click)
            prob_ind = np.argsort(prob_list)
            pre_ad = list()
            post_ad = list()
            # print prob_ind
            # print prob
            if user_tag == 'Unknown':
                for i in range(1, 11):
                    ad_id = ad_list[prob_ind[-i]]
                    if i<=5:
                        pre_ad.append(ad_id)
                    else:
                        post_ad.append(ad_id)
            else:
                i = 1
                # 选出第一排广告(只给出用户标签的商品排行)和第二排广告(包括前三个非用户标签的商品排行和两个随机的商品)
                while i<=len(ad_list):
                    ad_id = ad_list[prob_ind[-i]]
                    ad_tag = id_to_tag[ad_id]
                    if len(pre_ad)<5 and user_tag == ad_tag:
                        pre_ad.append(ad_id)
                    elif user_tag != ad_tag and len(post_ad)<3:
                        post_ad.append(ad_id)
                    if len(pre_ad)==5 and len(post_ad)==3:
                        break
                    i+=1
                for j in range(2):
                    ad_id = ad_list[random.randint(0, len(ad_list)-i-1)]
                    while ad_id in post_ad:
                        ad_id = ad_list[random.randint(0, len(ad_list)-i-1)]
                    post_ad.append(ad_id)


            # print pre_ad, post_ad
            user_behavior = (user_tag, user_sex)
            pre_ad = ','.join(pre_ad)
            post_ad = ','.join(post_ad)
            # 更新rank数据库
            db.updateRank(user_behavior, pre_ad, post_ad)


if __name__ == '__main__':
    ctr = CTR()
    ctr.userBehaviorCTR()

