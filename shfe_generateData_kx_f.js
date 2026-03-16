/*
 * @Description:
 * @Author: zhou.xiaowei@trs.com.cn
 * @Date: 2023-09-07 16:30:59
 */
Vue.component("kx-table-component", {
  template: '#kx-component',
  props: {
    current_date: {
      type: String,
      default: ''
    },
    side_type_select: {
      type: String,
      default: ''
    },
    productionClass: {
      type: String,
      default: 'all'
    }
  },
  watch: {
    current_date: {
      handler(newVal, oldVal) {
        this.type_select = 'all';
        this.form.searchCate = 'all'
        this.form.searchCateItem = '';
        this.recordCateIndex = 'all';
        this.showSelect = false;
        this.$nextTick(() => {
          this.showSelect = true;
        });

        // if( oldVal !== ''  ) {
        //   this.side_type_select = 'all';
        // }
        this.queryTableData_kx();
      }
    },
  },
  data() {
    return {
      type_select: 'all',
      showSelect: true, // 控制搜索条件的显示和隐藏
      loading: false, // 加载状态
      json: {}, // 原始数据
      name: "名字",
      data_path: '', // 路径
      isshowDouble: false, // 是否显示单双边
      singlenoteObj: {}, // 单双变对应的对象
      isShowReportMemo1: false, // 表格1备注是否显示
      reportMemo1: {}, // 表格1备注
      isShowReportMemo2: false, // 表格2备注是否显示
      reportMemo2: {}, // 表格1备注
      isShowReportMemo3: false, // 表格3备注是否显示
      reportMemo3: {}, // 表格1备注
      recordName: [], // 记录每个table下的name
      recordList: [], // 记录每个table下的具体内容
      resultList: [], // 最终的结果数组
      isShowMore1: true, // 备注的展开是否更多
      isShowMore2: false, // 备注的展开是否更多
      isShowMore3: false, // 备注的展开是否更多
      pro_list1: [], // 第二张表格的数据
      pro_list2: [], // 第三张表格的数据
      table3_date: '', // table3的时间
      noData: false, // 暂无数据
      isShowOtherTable: true, // 是否显示其他表格
      isShowExpend1: true, // 是否显示展开按钮
      isShowExpend2: true, // 是否显示展开按钮
      isShowExpend3: true, // 是否显示展开按钮
      // 新增参数
      isShowMobilePage: false,
      form: {
        searchCate: 'all',
        searchCateItem: ''
      },
      select_doc: {}, // 新增 记录品类信息
      select_arr1: {}, // 新增 记录大类信息
      select_arr2: {}, // 新增 记录小类信息
      recordCateIndex: 'all', // 新增
    };
  },
  mounted() {
    // this.queryTableData_kx();
    // 新增
    if (screenWidth < 750) {
      this.isShowMobilePage = true;
      this.select_doc = getProductList(enumObj.originalType.shfe, '1');
      this.select_arr1 = this.select_doc.name;
      this.select_arr2 = this.select_doc.list;
    } else {
      this.isShowMobilePage = false;
    }
  },

  methods: {
    // 数据筛选
    getProductionId_info: function getProductionId_info(id) {
      //console.log(id);
      this.type_select = id;
      if (this.type_select !== "all") {
        this.type_select = this.type_select.split("_")[0];
      }
      if (this.type_select === 'all') {
        this.isShowOtherTable = true;
      } else {
        this.isShowOtherTable = false;
      }
      this.handleJsonData();
      //console.log('this.type_select95...', this.type_select, this.resultList);
    },
    // 新增 金属、能源化工、金属
    handleCateTab: function handleCateTab(value) {
      this.recordCateIndex = value;
      if (value !== 'all') {
        this.form.searchCateItem = this.select_arr2[this.recordCateIndex][0].productid;
      } else {
        this.form.searchCateItem = 'all';
      }
      this.resultList = {};
      this.$nextTick(() => {
        this.getProductionId_info(this.form.searchCateItem);
      })
    },
    // 新增 种类： 铜...
    handleCateItemTab: function handleCateItemTab(value) {
      this.resultList = {};
      this.$nextTick(() => {
        this.getProductionId_info(value);
      })
    },

    // 新增 url携带参数，下拉框赋值处理
    handleselectdefault: function handleselectdefault(side_type_select) {
      let recordItemIndexList = [];
      recordItemIndexList = this.findElementWithPropertyIndex(this.select_arr2, 'productid', side_type_select)
      this.form.searchCate = recordItemIndexList[0];
      this.recordCateIndex = recordItemIndexList[0];
      this.$nextTick(() => {
        this.form.searchCateItem = side_type_select;
      });
    },
    // 新增
    findElementWithPropertyIndex: function findElementWithPropertyIndex(arr, propertyName, propertyValue, parentIndex = []) {
      for (let i = 0; i < arr.length; i++) {
        if (Array.isArray(arr[i])) {
          // 如果当前元素是数组，则递归调用
          const result = findElementWithPropertyIndex(arr[i], propertyName, propertyValue, [...parentIndex, i]);
          if (result !== null) {
            return result;
          }
        } else if (typeof arr[i] === 'object' && arr[i] !== null) {
          // 如果当前元素是对象，检查它的属性
          if (arr[i][propertyName] === propertyValue) {
            // 如果找到具有特定属性值的对象，返回当前下标和所属上一层数组的下标
            return [...parentIndex, i];
          }
        }
      }
      return null; // 如果没有找到具有特定属性值的对象，返回null
    },

    // 日交易快讯数据请求
    queryTableData_kx() {
      this.noData = false;
      this.loading = true;

      this.type_select = 'all';
      this.showSelect = false;
      this.$nextTick(function () {
        this.showSelect = true;
      });
      if (this.type_select === 'all') {
        this.isShowOtherTable = true
      } else {
        this.isShowOtherTable = false
      }
      const vm = this;
      // 报表数据查询
      $.ajax({
        url: api_futures_kx(vm.current_date),
        dataType: 'json',
        success: function (json) {
          vm.loading = false;
          //  没有数据的情况
          if (json.o_curinstrument.length === 0) {
            vm.noData = true;
            return;
          }
          vm.json = json;
          // console.log(vm.json);
          let pro_options_type =  pro_analysisUrl()
          if (vm.side_type_select && pro_options_type == '1' ) {
           if (screenWidth > 750) {
             vm.$refs.type_select.getProductionId(vm.side_type_select);
           } else {
             vm.handleselectdefault(vm.side_type_select);
             vm.getProductionId_info(vm.side_type_select);
           }
           return;
         }
          // 针对表格数据进行处理
          vm.handleJsonData();
        },
        error: function () {
          // 没有数据
          vm.loading = false;
          vm.noData = true;
        }
      });
    },

    // 是否展开备注
    isExpand(type) {
      const vm = this;
      if (type == '1') {
        vm.isShowMore1 = !vm.isShowMore1
      } else if (type == '2') {
        vm.isShowMore2 = !vm.isShowMore2
      } else {
        vm.isShowMore3 = !vm.isShowMore3
      }
    },
    // table首行特殊样式
    rowClassName({
      row,
      columnIndex
    }) {
      if (row.TYPE_LINE) {
        return "special_row_type"
      }
      if (row.DELIVERYMONTH) {
        if (row.DELIVERYMONTH.includes(enumObj.field_key_all_total) || row.DELIVERYMONTH.includes(enumObj.field_key_subtotal)) {
          return "isTotal"
        }
      }
      if (row.PRODUCTNAME) {
        if (row.PRODUCTNAME.includes(enumObj.field_key_all_total) || row.PRODUCTNAME.includes(enumObj.field_key_subtotal)) {
          return "isTotal"
        }
      }
    },

    // 处理报表数据
    handleJsonData() {
      // 表格处理
      let tableData = JSON.parse(JSON.stringify(this.json));
      // console.log(this.type_select);
      if (this.type_select !== 'all') {

        tableData.o_curinstrument = this.json.o_curinstrument.filter(item => {
          if( item.PRODUCTID.includes('_') ) {
            let pro_id_info = item.PRODUCTID.trim()
            let pro_id = pro_id_info.split("_")[0];
            return pro_id === this.type_select
          } else {
            return item.PRODUCTID.trim() === this.type_select
          }

        });
      }

      // 获取是否显示单双边备注的endeffectivedate
      this.singlenoteObj = getReportSingleDoubleMemo('shfe_kx', 'report_issinglenote');
      // 头部单双边备注示例, 动态
      // console.log(this.current_date, this.singlenoteObj.endeffectivedate);
      if (this.current_date < this.singlenoteObj.endeffectivedate) {
        this.isshowDouble = true;
      } else {
        this.isshowDouble = false;
      }

      // 第一张表格的数据
      const pro_list = tableData.o_curinstrument;
      // console.log(tableData);
      // 将数组分为多产品数组
      let only_info = listParamsRepeat(tableData.o_curinstrument, 'PRODUCTID');
      // 针对数组进行的保留小数点位数precision---字段的添加
      pro_precision(only_info, 'decimal_number');
      this.recordName = [];
      this.recordList = [];
      // 针对的是上海期货交易所期货合约行情的表格处理
      only_info.forEach(item => {
        let arrItem = {
          DELIVERYMONTH: this.isShowMobilePage ? (item.PRODUCTNAME) : ('商品名称:' + item.PRODUCTNAME),
          PRODUCTID: item.PRODUCTID,
          TYPE_LINE: true, // 首行商品名称的标识
          tas_start_date: '',
          isTasPro: false,
          isTasProShow: false,
        };
        let tas_item = getProductProp(item.PRODUCTID.trim(), enumObj.tas_start_date);
        if (tas_item) {
          arrItem.tas_start_date = tas_item;
        }

        if (item.TURNOVER !== undefined) {
          arrItem.TURNOVER = '';
        }

        if (item.PRODUCTID.includes(enumObj.field_key_tas)) {
          let pro_id = item.PRODUCTID.replace('_tas', '')
          let recordId = getProductByGroup(pro_id.trim(), '1');
          // 获取每一项里面的tas_start_date属性
          let str = getProductProp(recordId, enumObj.tas_start_date);
          item.precision = getProductProp(recordId, 'decimal_number');
          arrItem.tas_start_date = str;
          arrItem.isTasPro = true;

          // 当 tas品种（例如：PRODUCTGROUPID: "sc_tas",PRODUCTID: "sc_tas"）的品种属性(product_config.dat) tas_start_date 如下情况：
          //    1. product_config.dat 没有配置时, getProductProp() 返回 '' <= current_date ---> true
          //    2. product_config.dat 配置为''时, getProductProp() 返回 '' <= current_date ---> true
          // 会导致 <未启用的tas品种> (有三种情况：1.没有配置属性tas_start_date、2.tas_start_date为空、3.tas_start_date > current_date) 报表上显示了tas品种数据的情况，与实际不符
          if (arrItem.tas_start_date && arrItem.tas_start_date!='0')
            arrItem.isTasProShow = arrItem.tas_start_date <= this.current_date ? true : false;
        } else {
          if (item.PRODUCTID.includes('efp')) {
            let pro_id = item.PRODUCTID.replace('efp', '')
            let recordId = getProductByGroup(pro_id.trim(), '1');
            // 获取每一项里面的tas_start_date属性
            let str = getProductProp(recordId, enumObj.tas_start_date);
            item.precision = getProductProp(recordId, 'decimal_number')
            arrItem.tas_start_date = str;
          }
        }

        this.recordName.push(arrItem);

        let recordListItem = [];
        pro_list.forEach(m => {
          if (m.PRODUCTID.trim() === item.PRODUCTID.trim()) {
            m.precision = item.precision;
            recordListItem.push(m);
          }
        });
        this.recordList.push(recordListItem);
      });

      let recordlistInfo = JSON.parse(JSON.stringify(this.recordList));
      this.recordList.forEach((item, index) => {
        if (item.length == 1 && item.some(item => item.PRODUCTNAME === enumObj.field_key_all_total)) {
          recordlistInfo[index - 1].push(recordlistInfo[index][0]);
          recordlistInfo.splice(index, 1)
        }
      });
      this.resultList = [];
//       修复 为空会导致refs.report_memo1不加载，表1注释不显示
//       this.resultList = recordlistInfo;

      // 针对总计进行特殊处理
      this.recordName.forEach((item, index) => {
        if (item.PRODUCTID === enumObj.field_key_all_total) {
          this.recordName.splice(index, 1)
        }
      })
   
      this.$nextTick( () => {
        this.resultList = recordlistInfo;
        // 针对首行商品名称做处理
        this.resultList.forEach((item, index) => {
          item.unshift(this.recordName[index])
        });


          this.reportMemo1 = getReportMemo('shfe_kx', enumObj.report_1_note_total, this.current_date);
          this.$nextTick(() => {
            this.$refs.report_memo1 && this.$refs.report_memo1.handleBtn(this.reportMemo1);
          });
      });


      // console.log(this.resultList, this.recordName);


      // 第二张表格的数据
      this.pro_list1 = tableData.o_curproduct;
      pro_precision(this.pro_list1, 'decimal_number');

      // 第三张表格的数据
      this.pro_list2 = tableData.o_curmetalindex;
      this.table3_date = tableData.o_IMChangeDate;

      // 获取备注
//    this.reportMemo1 = getReportMemo('shfe_kx', enumObj.report_1_note_total, this.current_date);
      this.reportMemo2 = getReportMemo('shfe_kx', enumObj.report_2_note_total, this.current_date);
      this.reportMemo3 = getReportMemo('shfe_kx', enumObj.report_3_note_total, this.current_date);

//       传递备注信息到公共备注组件中去
//       this.$nextTick(() => {
//         this.$refs.report_memo1 && this.$refs.report_memo1.handleBtn(this.reportMemo1);
//       })

      if (this.type_select === 'all') {
        this.$nextTick(() => {
          this.$refs.report_memo2.handleBtn(this.reportMemo2);
          this.$refs.report_memo3.handleBtn(this.reportMemo3);
        })
      }

    },


    // 单元格合并
    arraySpanMethod({
      row,
      column,
      rowIndex,
      columnIndex,
      index
    }) {
      // return [1, 1];
    },
    headerStyle({
      row,
      colunm,
      rowIndex,
      columnIndex
    }) {
      // if (row[columnIndex].property === 'OPENINTEREST') {
      //   console.log(row[columnIndex]);
      //   row[columnIndex].rowSpan = 2
      // }
      // if (row[columnIndex].property === 'OPENINTERESTCHG') {
      //   console.log(row[columnIndex]);
      //   return {
      //     display: 'none'
      //   }
      //   // row[columnIndex].colSpan = 0
      //   // row[columnIndex].rowSpan = 0
      // }
    },

    // 整个页面打印
    printTable() {

      // 打印设置：表头字段'持仓手/变化'拼接
      this.assemblageHeaderKey();
      // 全局方法-打印
      printTable();

      // kx：打印后，切换品种，'TAS成交手'字段通过v-if判断不能正常展示，重新赋值可重新渲染table
      let list = JSON.parse(JSON.stringify(this.resultList));
      this.resultList = [];
      setTimeout(() => { 
        this.resultList = list;
      }, 0);
    },
    
    // 打印设置：表头字段'持仓手/变化'拼接
    assemblageHeaderKey(){
      // $(".kx_index_table").css('border','5px solid red');
      $(".kx_index_table .el-table .el-table__header-wrapper thead tr th:nth-last-child(3)").css('padding-right','unset').css('border-right','unset');
      $(".kx_index_table .el-table .el-table__header-wrapper thead tr th:nth-last-child(3)>div").css('text-align','right').css('padding-right','unset');
      $(".kx_index_table .el-table .el-table__header-wrapper thead tr th:nth-last-child(2)").css('padding-left','unset');
      $(".kx_index_table .el-table .el-table__header-wrapper thead tr th:nth-last-child(2)>div").css('text-align','left').css('padding-left','unset');
    },

    // 导出excell和txt
    exportExcel(name, type) {
      // 全局方法-导出excell和txt
      exportExcel(name, type);
    }
  },
});
