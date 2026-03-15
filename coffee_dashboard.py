ValueError: This app has encountered an error. The original error message is redacted to prevent data leaks. Full error details have been recorded in the logs (if you're on Streamlit Cloud, click on 'Manage app' in the lower right of your app).
Traceback:
File "/mount/src/cafe-sales-tracker/coffee_dashboard.py", line 206, in <module>
    view_dashboard()
    ~~~~~~~~~~~~~~^^
File "/mount/src/cafe-sales-tracker/coffee_dashboard.py", line 138, in view_dashboard
    df_base = logic_clean_data(st.session_state.sales_data)
File "/mount/src/cafe-sales-tracker/coffee_dashboard.py", line 76, in logic_clean_data
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目'))
    ~~^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 4322, in __setitem__
    self._set_item(key, value)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 4535, in _set_item
    value, refs = self._sanitize_column(value)
                  ~~~~~~~~~~~~~~~~~~~~~^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 5285, in _sanitize_column
    return _reindex_for_setitem(value, self.index)
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 12719, in _reindex_for_setitem
    raise err
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/frame.py", line 12714, in _reindex_for_setitem
    reindexed_value = value.reindex(index)._values
                      ~~~~~~~~~~~~~^^^^^^^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/series.py", line 5172, in reindex
    return super().reindex(
           ~~~~~~~~~~~~~~~^
        index=index,
        ^^^^^^^^^^^^
    ...<5 lines>...
        tolerance=tolerance,
        ^^^^^^^^^^^^^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/generic.py", line 5632, in reindex
    return self._reindex_axes(
           ~~~~~~~~~~~~~~~~~~^
        axes, level, limit, tolerance, method, fill_value, copy
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    ).__finalize__(self, method="reindex")
    ^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/generic.py", line 5655, in _reindex_axes
    new_index, indexer = ax.reindex(
                         ~~~~~~~~~~^
        labels, level=level, limit=limit, tolerance=tolerance, method=method
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
File "/home/adminuser/venv/lib/python3.13/site-packages/pandas/core/indexes/base.py", line 4436, in reindex
    raise ValueError("cannot reindex on an axis with duplicate labels")
